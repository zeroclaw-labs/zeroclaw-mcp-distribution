#!/usr/bin/env python3
"""Publish a qualified, immutable release using npm's GitHub OIDC identity."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import urllib.error
import urllib.request
import zipfile

REPO = "zeroclaw-labs/zeroclaw-mcp-distribution"
PACKAGE = "@zeroclaw-labs/zeroclaw-mcp"
VERSION = r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-alpha\.(0|[1-9][0-9]*))?"
TARGETS = ("aarch64-apple-darwin", "aarch64-unknown-linux-gnu", "x86_64-unknown-linux-gnu")
MAX_BYTES = 64 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command(args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def gh_json(*args):
    return json.loads(command(["gh", *args], capture_output=True).stdout)


def optional_api(path):
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=60)
    if result.returncode and "HTTP 404" in result.stderr:
        return None
    require(result.returncode == 0, "GitHub identity lookup failed")
    return json.loads(result.stdout)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def version_key(version):
    match = re.fullmatch(VERSION, version)
    require(match is not None, "Expected a canonical MCP stable or alpha version")
    major, minor, patch, alpha = match.groups()
    return (int(major), int(minor), int(patch), alpha is None, int(alpha or 0))


def validate_metadata(release, tag):
    version = tag.removeprefix("v")
    version_key(version)
    require(tag == "v" + version, "Expected an exact release tag")
    require(release.get("schema") == "zeroclaw-mcp-public-release/v1"
            and release.get("version") == version and release.get("qualified") is True,
            "Release is not qualified for this tag")
    npm = release.get("npm", {})
    require(npm.get("name") == PACKAGE and npm.get("version") == version,
            "Release npm identity differs")
    for value in (npm.get("sha256"), release.get("pluginZip", {}).get("sha256")):
        require(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value), "Invalid artifact digest")
    for key in ("assemblySource", "runtimeSource"):
        require(isinstance(release.get(key), str) and re.fullmatch(r"[a-f0-9]{40}", release[key]),
                "Invalid source identity")
    version_key(release["runtimeVersion"])
    integrity = npm.get("integrity", "")
    require(integrity.startswith("sha512-")
            and len(base64.b64decode(integrity[7:], validate=True)) == 64, "Invalid npm integrity")
    return release


def artifact_names(version):
    tar = f"zeroclaw-labs-zeroclaw-mcp-{version}.tgz"
    zipped = f"zeroclaw-plugin-{version}.zip"
    return [tar, tar + ".sha256", zipped, zipped + ".sha256", "install.sh"]


def release_identity(tag):
    version_key(tag.removeprefix("v"))
    require(tag.startswith("v"), "Expected an exact release tag")
    record = optional_api(f"repos/{REPO}/releases/tags/{tag}")
    # The tag endpoint omits drafts; list access still requires release-write
    # visibility from the workflow's own repository token.
    if record is None:
        for page in range(1, 11):
            rows = gh_json("api", f"repos/{REPO}/releases?per_page=100&page={page}")
            matches = [row for row in rows if row["tag_name"] == tag]
            require(len(matches) <= 1, "Ambiguous draft release tag")
            if matches:
                record = matches[0]
                break
            if len(rows) < 100:
                break
    require(record is not None, "Prepared release not found")
    require(record["tag_name"] == tag and re.fullmatch(r"[a-f0-9]{40}", record["target_commitish"]),
            "Release must point to an exact source commit")
    ref = optional_api(f"repos/{REPO}/git/ref/tags/{tag}")
    if ref is None:
        # GitHub creates a draft's tag only when the release is published.
        require(record["draft"] is True, "Published release tag is missing")
        return record
    obj = ref["object"]
    for _ in range(4):
        if obj["type"] == "commit":
            break
        require(obj["type"] == "tag" and re.fullmatch(r"[a-f0-9]{40}", obj["sha"]), "Invalid release tag object")
        obj = gh_json("api", f"repos/{REPO}/git/tags/{obj['sha']}")["object"]
    require(obj["type"] == "commit" and obj["sha"] == record["target_commitish"], "Release tag source changed")
    return record


def read_regular(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= MAX_BYTES,
            "Unsafe or oversized release file")
    return path.read_bytes()


def validate_artifacts(root, release):
    version = release["version"]
    tar_name, _, zip_name, _, _ = artifact_names(version)
    tar_raw, zip_raw = read_regular(root / tar_name), read_regular(root / zip_name)
    require(digest(tar_raw) == release["npm"]["sha256"]
            and digest(zip_raw) == release["pluginZip"]["sha256"], "Release artifact checksum mismatch")
    require("sha512-" + base64.b64encode(hashlib.sha512(tar_raw).digest()).decode()
            == release["npm"]["integrity"], "npm integrity mismatch")
    for name, raw in ((tar_name, tar_raw), (zip_name, zip_raw)):
        require(read_regular(root / (name + ".sha256")).decode().split() == [digest(raw), name],
                "Checksum sidecar differs")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(tar_raw), mode="r:gz") as archive:
        total = 0
        for member in archive:
            require(member.isfile() and member.name.startswith("package/") and not member.pax_headers,
                    "Unsafe npm archive member")
            name = member.name.removeprefix("package/")
            require(name and all(p not in ("", ".", "..") for p in name.split("/"))
                    and name not in files and member.mode in (0o644, 0o755)
                    and 0 < member.size <= 32 * 1024 * 1024, "Invalid npm archive path, size or mode")
            total += member.size
            require(total <= MAX_BYTES and len(files) < 30, "Unexpected npm archive inventory")
            files[name] = (archive.extractfile(member).read(), member.mode)
    names = {"package.json", "cli.cjs", "installer.cjs", "run.sh", "codex.mcp.json", "claude.mcp.json",
             ".codex-plugin/plugin.json", ".claude-plugin/plugin.json", "skills/setup/SKILL.md",
             "README.md", "LICENSE-MIT", "LICENSE-APACHE", "public-provenance.json"}
    runtime = {"package.json", "launcher.cjs", "README.md", "LICENSE-MIT", "LICENSE-APACHE",
               "payload-lock.json", "provenance.json", "generic-provenance.json"}
    for target in TARGETS:
        archive = f"payloads/zeroclaw-mcp-{release['runtimeVersion']}-{target}.tar.gz"
        runtime.update((archive, archive + ".sha256", f"launchers/{target}/zeroclaw-plugin-launcher"))
    require(set(files) == names | {"runtime/" + n for n in runtime}, "Public package file inventory differs")
    with zipfile.ZipFile(io.BytesIO(zip_raw)) as archive:
        members = archive.infolist()
        require(len(members) == len(files) and {m.filename for m in members} == set(files),
                "Plugin archive inventory differs")
        for member in members:
            raw, mode = files[member.filename]
            require(member.compress_type == zipfile.ZIP_STORED and not member.flag_bits & 1
                    and stat.S_ISREG(member.external_attr >> 16)
                    and stat.S_IMODE(member.external_attr >> 16) == mode
                    and member.file_size == len(raw) and archive.read(member) == raw,
                    "Plugin and npm archive bytes or modes differ")
    package = json.loads(files["package.json"][0])
    require(package.get("name") == PACKAGE and package.get("version") == version
            and package.get("mcpName") == "io.github.zeroclaw-labs/zeroclaw-mcp"
            and package.get("repository", {}).get("url") == f"https://github.com/{REPO}.git"
            and package.get("publishConfig") == {"access": "public", "registry": "https://registry.npmjs.org"}
            and not any(k in package for k in ("scripts", "dependencies", "devDependencies", "optionalDependencies",
                                              "peerDependencies", "bundledDependencies", "workspaces")),
            "Public npm manifest contract differs")
    proof = json.loads(files["public-provenance.json"][0])
    require(proof.get("schema") == "zeroclaw-mcp-public-package/v1"
            and proof.get("assembly_source_commit") == release["assemblySource"]
            and proof.get("assembly_source_dirty") is False and proof.get("version") == version
            and proof.get("server_version") == release["runtimeVersion"]
            and proof.get("server_source_commit") == release["runtimeSource"], "Package provenance differs")
    require(set(proof.get("files", {})) == set(files) - {"public-provenance.json"}, "Provenance inventory differs")
    for name, pin in proof["files"].items():
        raw, mode = files[name]
        require(pin == {"size": len(raw), "sha256": digest(raw), "mode": mode}, "Provenance file pin differs")
    bootstrap = read_regular(root / "install.sh")
    require(f"/releases/download/v{version}/{tar_name}".encode() in bootstrap
            and release["npm"]["sha256"].encode() in bootstrap, "Shell installer does not pin this release")
    return files


def prepare(tag, root):
    version_key(tag.removeprefix("v"))
    require(tag.startswith("v"), "Expected an exact release tag")
    record = release_identity(tag)
    content = gh_json("api", f"repos/{REPO}/contents/release.json?ref={record['target_commitish']}")
    release = validate_metadata(json.loads(base64.b64decode(content["content"])), tag)
    root.mkdir(parents=True, exist_ok=False)
    names = artifact_names(release["version"])
    assets = {a["name"]: a for a in record["assets"]}
    require(all(n in assets for n in names), "Release is missing expected assets")
    for name in names:
        command(["gh", "release", "download", tag, "--repo", REPO, "--pattern", name, "--dir", str(root)])
        advertised = assets[name].get("digest")
        require(advertised == "sha256:" + digest(read_regular(root / name)), "GitHub asset digest differs")
    validate_artifacts(root, release)
    (root / "release.json").write_text(json.dumps(release, indent=2) + "\n")
    receipt = {"id": record["id"], "source": record["target_commitish"],
               "assets": {name: {k: assets[name][k] for k in ("id", "digest", "size")} for name in names}}
    (root / "github-release.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a") as stream:
            stream.write(f"version={release['version']}\n")
    return release


def registry_json(suffix=""):
    url = "https://registry.npmjs.org/@zeroclaw-labs%2fzeroclaw-mcp" + suffix
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def verify_registry(release, root):
    metadata = registry_json("/" + release["version"])
    require(metadata is not None and metadata.get("name") == PACKAGE
            and metadata.get("version") == release["version"]
            and metadata.get("dist", {}).get("integrity") == release["npm"]["integrity"],
            "Published npm version is absent or has different integrity")
    url = metadata["dist"]["tarball"]
    require(url.startswith("https://registry.npmjs.org/@zeroclaw-labs/zeroclaw-mcp/-/"), "Unexpected registry download URL")
    with urllib.request.urlopen(url, timeout=180) as response:
        raw = response.read(MAX_BYTES + 1)
    require(raw == read_regular(root / artifact_names(release["version"])[0]), "Registry bytes differ from qualified bytes")
    return metadata


def publish(root):
    release = json.loads((root / "release.json").read_text())
    validate_metadata(release, "v" + release["version"])
    validate_artifacts(root, release)
    record = release_identity("v" + release["version"])
    receipt = json.loads((root / "github-release.json").read_text())
    assets = {a["name"]: a for a in record["assets"]}
    require(record["id"] == receipt["id"] and record["target_commitish"] == receipt["source"]
            and set(receipt["assets"]) == set(artifact_names(release["version"]))
            and all({k: assets.get(n, {}).get(k) for k in ("id", "digest", "size")} == pin
                    for n, pin in receipt["assets"].items()), "GitHub release changed after verification")
    metadata = registry_json() or {}
    for tag in ("alpha", "latest"):
        current = metadata.get("dist-tags", {}).get(tag)
        require(current is None or version_key(current) <= version_key(release["version"]),
                "Refusing to move a newer npm tag backwards")
    existing = registry_json("/" + release["version"])
    if existing is None:
        command(["npm", "publish", str(root / artifact_names(release["version"])[0]),
                 "--access", "public", "--tag", "alpha", "--ignore-scripts"])
    verify_registry(release, root)
    metadata = registry_json()
    for tag in ("alpha", "latest"):
        current = metadata.get("dist-tags", {}).get(tag)
        require(current is None or version_key(current) <= version_key(release["version"]),
                "Refusing to move a newer npm tag backwards")
        if current != release["version"]:
            command(["npm", "dist-tag", "add", f"{PACKAGE}@{release['version']}", tag])
    tags = registry_json()["dist-tags"]
    require(all(tags.get(t) == release["version"] for t in ("latest", "alpha")), "npm tag update did not settle")
    command(["gh", "release", "edit", "v" + release["version"], "--repo", REPO, "--draft=false"])
    return {"published": True, "version": release["version"], "sha256": release["npm"]["sha256"]}


def promote(tag):
    record = release_identity(tag)
    require(not record["draft"], "GitHub release must be public before catalog promotion")
    content = gh_json("api", f"repos/{REPO}/contents/release.json?ref={tag}")
    release = validate_metadata(json.loads(base64.b64decode(content["content"])), tag)
    metadata = registry_json("/" + release["version"])
    require(metadata and metadata["dist"]["integrity"] == release["npm"]["integrity"], "npm must be public before catalogs")
    current = gh_json("api", f"repos/{REPO}/contents/release.json?ref=main")
    current = json.loads(base64.b64decode(current["content"]))
    require(version_key(current["version"]) <= version_key(release["version"]), "Refusing catalog downgrade")
    if current == release:
        command(["gh", "workflow", "run", "verify-public-install.yml", "--repo", REPO, "--ref", "main"])
        command(["gh", "workflow", "run", "publish-registry.yml", "--repo", REPO, "--ref", "main"])
        return {"catalogs_already_current": True}
    prs = gh_json("pr", "list", "--repo", REPO, "--state", "open", "--json", "number,headRefOid,headRefName,isDraft")
    matches = [p for p in prs if p["headRefOid"] == record["target_commitish"]]
    require(len(matches) == 1, "Expected one catalog PR at the exact release commit")
    pr = matches[0]
    if pr["isDraft"]:
        command(["gh", "pr", "ready", str(pr["number"]), "--repo", REPO])
    command(["gh", "pr", "merge", str(pr["number"]), "--repo", REPO, "--squash",
             "--match-head-commit", pr["headRefOid"]])
    result = gh_json("pr", "view", str(pr["number"]), "--repo", REPO, "--json", "state")
    require(result["state"] == "MERGED", "Catalog PR is still awaiting repository merge requirements; rerun after they pass")
    command(["gh", "workflow", "run", "verify-public-install.yml", "--repo", REPO, "--ref", "main"])
    command(["gh", "workflow", "run", "publish-registry.yml", "--repo", REPO, "--ref", "main"])
    return {"catalog_pr": pr["number"], "merged": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "validate", "publish", "promote"))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--directory", type=Path, default=Path("release-input"))
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare(args.tag, args.directory)
    elif args.action == "promote":
        result = promote(args.tag)
    else:
        release = validate_metadata(json.loads((args.directory / "release.json").read_text()), args.tag)
        result = publish(args.directory) if args.action == "publish" else {"validated_files": len(validate_artifacts(args.directory, release))}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

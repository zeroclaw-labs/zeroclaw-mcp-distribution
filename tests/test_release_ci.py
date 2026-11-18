"""Release identity and retry guards; no npm/GitHub writes are made."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest import mock
import urllib.error
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_ci", ROOT / "scripts/release_ci.py")
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.version = "0.1.0-alpha.6"
        self.release = {"schema": "zeroclaw-mcp-public-release/v1", "qualified": True,
                        "version": self.version, "assemblySource": "a" * 40, "runtimeSource": "b" * 40,
                        "runtimeVersion": "0.1.0-alpha.9", "npm": {"name": ci.PACKAGE, "version": self.version},
                        "pluginZip": {}}
        self.files = {n: (b"fixture\n", 0o644) for n in (
            "package.json", "cli.cjs", "installer.cjs", "run.sh", "codex.mcp.json", "claude.mcp.json",
            ".codex-plugin/plugin.json", ".claude-plugin/plugin.json", "skills/setup/SKILL.md",
            "README.md", "LICENSE-MIT", "LICENSE-APACHE")}
        self.manifest = {"name": ci.PACKAGE, "version": self.version,
                         "mcpName": "io.github.zeroclaw-labs/zeroclaw-mcp",
                         "repository": {"url": f"https://github.com/{ci.REPO}.git"},
                         "publishConfig": {"access": "public", "registry": "https://registry.npmjs.org"}}
        for n in ("package.json", "launcher.cjs", "README.md", "LICENSE-MIT", "LICENSE-APACHE",
                  "payload-lock.json", "provenance.json", "generic-provenance.json"):
            self.files["runtime/" + n] = (b"runtime fixture\n", 0o644)
        for target in ci.TARGETS:
            name = f"runtime/payloads/zeroclaw-mcp-0.1.0-alpha.9-{target}.tar.gz"
            self.files[name] = (b"archive fixture", 0o644)
            self.files[name + ".sha256"] = (b"hash fixture", 0o644)
            self.files[f"runtime/launchers/{target}/zeroclaw-plugin-launcher"] = (b"binary fixture", 0o755)
        self.pack()

    def pack(self, duplicate=False, linked=False, proof_override=None):
        self.files["package.json"] = (json.dumps(self.manifest).encode(), 0o644)
        self.files.pop("public-provenance.json", None)
        proof = {"schema": "zeroclaw-mcp-public-package/v1", "assembly_source_commit": "a" * 40,
                 "assembly_source_dirty": False, "version": self.version, "server_version": "0.1.0-alpha.9",
                 "server_source_commit": "b" * 40,
                 "files": {n: {"size": len(raw), "sha256": ci.digest(raw), "mode": mode}
                           for n, (raw, mode) in self.files.items()}}
        proof.update(proof_override or {})
        self.files["public-provenance.json"] = (json.dumps(proof).encode(), 0o644)
        tar_name, _, zip_name, _, _ = ci.artifact_names(self.version)
        with tarfile.open(self.root / tar_name, "w:gz") as archive:
            rows = list(self.files.items())
            if duplicate: rows.append(rows[0])
            for n, (raw, mode) in rows:
                item = tarfile.TarInfo("package/" + n)
                item.size, item.mode = len(raw), mode
                if linked and n == "run.sh":
                    item.type, item.linkname, item.size = tarfile.SYMTYPE, "/tmp/foreign", 0
                archive.addfile(item, io.BytesIO(raw))
        with zipfile.ZipFile(self.root / zip_name, "w", compression=zipfile.ZIP_STORED) as archive:
            for n, (raw, mode) in self.files.items():
                item = zipfile.ZipInfo(n)
                item.external_attr = (stat.S_IFREG | mode) << 16
                archive.writestr(item, raw)
        tar_raw = (self.root / tar_name).read_bytes()
        self.release["npm"].update(sha256=ci.digest(tar_raw), integrity="sha512-" + base64.b64encode(ci.hashlib.sha512(tar_raw).digest()).decode())
        self.release["pluginZip"]["sha256"] = ci.digest((self.root / zip_name).read_bytes())
        for name in (tar_name, zip_name):
            (self.root / (name + ".sha256")).write_text(ci.digest((self.root / name).read_bytes()) + "  " + name + "\n")
        (self.root / "install.sh").write_text(f"#!/bin/sh\n# /releases/download/v{self.version}/{tar_name}\n# {self.release['npm']['sha256']}\n")
        (self.root / "release.json").write_text(json.dumps(self.release))

    def test_qualified_exact_inventory_is_accepted(self):
        ci.validate_metadata(self.release, "v" + self.version)
        self.assertEqual(len(ci.validate_artifacts(self.root, self.release)), 30)

    def test_unqualified_wrong_tag_and_malformed_versions_are_refused(self):
        for version in ("01.0.0", "0.1.0-alpha.06", "0.1.0;echo bad", "../0.1.0", "0.1.0\nvalue=bad"):
            with self.subTest(version=version), self.assertRaises(ValueError): ci.version_key(version)
        for change in ({"qualified": False}, {"assemblySource": "main"}, {"version": "0.1.0-alpha.7"}):
            with self.assertRaises(ValueError): ci.validate_metadata({**self.release, **change}, "v" + self.version)

    def test_changed_bytes_duplicate_entries_and_links_are_refused(self):
        tar = self.root / ci.artifact_names(self.version)[0]
        tar.write_bytes(tar.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "checksum"): ci.validate_artifacts(self.root, self.release)
        self.pack(duplicate=True)
        with self.assertRaises(ValueError): ci.validate_artifacts(self.root, self.release)
        self.pack(linked=True)
        with self.assertRaises(ValueError): ci.validate_artifacts(self.root, self.release)

    def test_scripts_and_false_source_proofs_cannot_be_rehashed_into_acceptance(self):
        self.manifest["scripts"] = {"prepublishOnly": "unexpected-command"}
        self.pack()
        with self.assertRaisesRegex(ValueError, "manifest"): ci.validate_artifacts(self.root, self.release)
        del self.manifest["scripts"]
        self.pack(proof_override={"assembly_source_dirty": True})
        with self.assertRaisesRegex(ValueError, "provenance"): ci.validate_artifacts(self.root, self.release)

    def receipt(self):
        record = {"id": 42, "target_commitish": "c" * 40, "assets": []}
        pins = {}
        for i, name in enumerate(ci.artifact_names(self.version)):
            pin = {"id": i + 1, "digest": "sha256:" + ci.digest((self.root / name).read_bytes()),
                   "size": (self.root / name).stat().st_size}
            pins[name] = pin
            record["assets"].append({"name": name, **pin})
        (self.root / "github-release.json").write_text(json.dumps({"id": 42, "source": "c" * 40, "assets": pins}))
        return record

    def test_newer_tags_stop_before_any_publication(self):
        with mock.patch.object(ci, "release_identity", return_value=self.receipt()), \
             mock.patch.object(ci, "registry_json", return_value={"dist-tags": {"latest": "0.1.0-alpha.7"}}), \
             mock.patch.object(ci, "command") as mutate:
            with self.assertRaisesRegex(ValueError, "backwards"): ci.publish(self.root)
            mutate.assert_not_called()

    def test_existing_different_package_is_never_overwritten(self):
        metadata = {"name": ci.PACKAGE, "version": self.version, "dist": {"integrity": "wrong"}}
        with mock.patch.object(ci, "release_identity", return_value=self.receipt()), \
             mock.patch.object(ci, "registry_json", side_effect=[{"dist-tags": {}}, metadata, metadata]), \
             mock.patch.object(ci, "command") as mutate:
            with self.assertRaisesRegex(ValueError, "integrity"): ci.publish(self.root)
            mutate.assert_not_called()

    def test_changed_release_identity_stops_before_npm(self):
        record = self.receipt()
        record["assets"][0]["digest"] = "sha256:" + "f" * 64
        with mock.patch.object(ci, "release_identity", return_value=record), mock.patch.object(ci, "command") as mutate:
            with self.assertRaisesRegex(ValueError, "changed after"): ci.publish(self.root)
            mutate.assert_not_called()

    def test_drafts_may_not_have_created_their_tag_yet(self):
        record = {"tag_name": "v" + self.version, "target_commitish": "c" * 40, "draft": True}
        with mock.patch.object(ci, "gh_json", return_value=[record]), mock.patch.object(ci, "optional_api", return_value=None):
            self.assertEqual(ci.release_identity("v" + self.version), record)
            record["draft"] = False
            with self.assertRaisesRegex(ValueError, "tag is missing"): ci.release_identity("v" + self.version)

    def test_registry_retries_reuse_only_the_matching_active_version(self):
        server = {"$schema": "schema", "name": "io.github.zeroclaw-labs/zeroclaw-mcp", "version": self.version,
                  "packages": [{"registryType": "npm", "identifier": ci.PACKAGE, "version": self.version}]}
        row = {"server": {k: v for k, v in server.items() if k != "$schema"},
               "_meta": {"io.modelcontextprotocol.registry/official": {"status": "active"}}}
        with mock.patch.object(ci.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(row).encode())) as fetch:
            self.assertFalse(ci.registry_status(server)["needed"])
            self.assertIn("io.github.zeroclaw-labs%2Fzeroclaw-mcp/versions/", fetch.call_args.args[0])
        row["server"]["packages"][0]["version"] = "0.1.0-alpha.5"
        expected = {**server, "packages": [{"registryType": "npm", "identifier": ci.PACKAGE, "version": self.version}]}
        with mock.patch.object(ci.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(row).encode())):
            with self.assertRaisesRegex(ValueError, "conflicts"): ci.registry_status(expected)
        row["server"]["packages"] = expected["packages"]
        row["_meta"]["io.modelcontextprotocol.registry/official"]["status"] = "deleted"
        with mock.patch.object(ci.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(row).encode())):
            with self.assertRaisesRegex(ValueError, "not active"): ci.registry_status(expected)

    def test_registry_network_errors_are_not_mistaken_for_missing_versions(self):
        server = {"name": "io.github.zeroclaw-labs/zeroclaw-mcp", "version": self.version}
        with mock.patch.object(ci.urllib.request, "urlopen", side_effect=urllib.error.HTTPError("url", 404, "missing", {}, None)):
            self.assertTrue(ci.registry_status(server)["needed"])
        with mock.patch.object(ci.urllib.request, "urlopen", side_effect=urllib.error.HTTPError("url", 503, "unavailable", {}, None)):
            with self.assertRaises(urllib.error.HTTPError): ci.registry_status(server)

    def test_catalog_retry_binds_checks_to_verified_main_snapshot_without_another_merge(self):
        record = {**self.receipt(), "draft": False}
        content = {"content": base64.b64encode(json.dumps(self.release).encode()).decode()}
        with mock.patch.object(ci, "release_identity", return_value=record), \
             mock.patch.object(ci, "registry_json", return_value={"dist": {"integrity": self.release["npm"]["integrity"]}}), \
             mock.patch.object(ci, "gh_json", side_effect=[content, {"object": {"sha": "d" * 40}}, content]), \
             mock.patch.object(ci, "command") as mutate:
            result = ci.promote("v" + self.version, self.root)
            self.assertEqual(result, {"catalogs_already_current": True, "catalog_commit": "d" * 40})
            mutate.assert_not_called()

    def test_catalog_checks_use_the_actual_merge_commit(self):
        record = {**self.receipt(), "draft": False}
        content = {"content": base64.b64encode(json.dumps(self.release).encode()).decode()}
        old = {"content": base64.b64encode(b'{"version":"0.1.0-alpha.5"}').decode()}
        pr = {"number": 1, "headRefOid": "c" * 40, "headRefName": "release/alpha6", "isDraft": True}
        with mock.patch.object(ci, "release_identity", return_value=record), \
             mock.patch.object(ci, "registry_json", return_value={"dist": {"integrity": self.release["npm"]["integrity"]}}), \
             mock.patch.object(ci, "gh_json", side_effect=[content, {"object": {"sha": "d" * 40}}, old, [pr],
                                                         {"state": "MERGED", "mergeCommit": {"oid": "e" * 40}}, content]), \
             mock.patch.object(ci, "command"):
            result = ci.promote("v" + self.version, self.root)
            self.assertEqual(result["catalog_commit"], "e" * 40)
            self.assertTrue(result["merged"])


if __name__ == "__main__": unittest.main()

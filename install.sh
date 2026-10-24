#!/bin/sh
set -eu
case "$*" in --help|-h) printf '%s\n' 'Usage: sh install.sh --codex | --claude | --codex --claude'; exit 0 ;; esac
if [ "$#" -eq 0 ]; then printf '%s\n' 'Choose --codex, --claude, or both.' >&2; exit 1; fi
for option in "$@"; do
  case "$option" in --codex|--claude) ;; *) printf '%s\n' "Unknown option: $option" >&2; exit 1 ;; esac
done
command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 || { printf '%s\n' 'Install Node.js 22 or newer, then run this installer again.' >&2; exit 1; }
node -e 'if (Number(process.versions.node.split(".")[0]) < 22) { console.error("Node.js 22 or newer is required"); process.exit(1); }'
command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required to download the package.' >&2; exit 1; }
zeroclaw_install_dir=$(mktemp -d "${TMPDIR:-/tmp}/zeroclaw-install.XXXXXXXX")
cleanup() { rm -f "$zeroclaw_install_dir/package.tgz"; rmdir "$zeroclaw_install_dir"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf '%s\n' 'Downloading ZeroClaw 0.1.0-alpha.4...'
curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 --connect-timeout 20 --max-time 900 --retry 2 --output "$zeroclaw_install_dir/package.tgz" 'https://github.com/zeroclaw-labs/zeroclaw-mcp-distribution/releases/download/v0.1.0-alpha.4/zeroclaw-labs-zeroclaw-mcp-0.1.0-alpha.4.tgz'
node -e 'const fs=require("node:fs"),c=require("node:crypto"); if(c.createHash("sha256").update(fs.readFileSync(process.argv[1])).digest("hex")!==process.argv[2]) { console.error("Package checksum mismatch; installation stopped"); process.exit(1); }' "$zeroclaw_install_dir/package.tgz" '2c5b45a1c63f0363348bf0e2923793660bc5f7bb10d4f00a6e837d7b9a2a417a'
npm exec --yes --package="$zeroclaw_install_dir/package.tgz" -- zeroclaw-mcp install "$@"

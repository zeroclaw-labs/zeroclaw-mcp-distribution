# ZeroClaw MCP

> Private distribution staging: no public package or marketplace is available yet. The commands below describe the release candidate. Publication remains gated by runtime qualification and package ownership.

Your hardware. Your memories. Your choice of model.

Install the plugin for your agent:

```sh
npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.3 install --codex
# Or:
npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.3 install --claude
```

Choose both flags to install for both clients. The installer verifies the package, keeps a persistent copy outside npm's cache, backs up the affected client settings, and uses the client's plugin commands. It checks the bundled MCP without contacting a target. Restart your client and ask: **Set up ZeroClaw. Call it Home Lab and use my saved lab connection.** In Claude Code, you can also run `/zeroclaw:setup`.

The installer requires Node.js 22 or newer and the selected client CLI. Supported controllers are Apple Silicon macOS and ARM64/x86-64 GNU Linux with glibc 2.39 or newer. Native plugin startup needs no Node, Python, compiler, or additional download. Target operations retain the existing OpenSSH, supported GitHub CLI, and prepared Linux-account prerequisites.

For other MCP clients, configure a stdio server with command `npx` and arguments `["-y", "@zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.3", "mcp"]`. The server runs locally; a package download URL is not a hosted MCP endpoint.

## Permissions and updates

Installing the plugin does not authorize management of a machine. Setup proposes a named connection in chat, then the client asks you to review exact permissions. Credentials stay in private local files. The plugin has no hooks or automatic tool approvals.

Run the installation command again with a later published version to update. The installer retains earlier package versions and configuration backups. An existing marketplace or MCP registration with a conflicting source is reported for review rather than silently replaced. Existing manager state remains under `~/.zeroclaw-manager/`, and the verified native runtime remains under `~/.local/lib/zeroclaw-mcp/`.

Release notes and direct downloads are available in the [distribution repository](https://github.com/zeroclaw-labs/zeroclaw-mcp-distribution). This package reuses the verified MCP runtime 0.1.0-alpha.6 and original native launchers; its own package/plugin version is 0.1.0-alpha.3.

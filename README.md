# ZeroClaw MCP

Your hardware. Your memories. Your choice of model.

Install the plugin for your agent:

```sh
npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.4 install --codex
# Or:
npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.4 install --claude
```

Choose both flags to install for both clients. The installer verifies the package, keeps a persistent copy outside npm's cache, backs up the affected client settings, and uses the client's plugin commands. It checks the bundled MCP without contacting a target. Restart your client and ask: **Set up ZeroClaw. Call it Home Lab and use my saved lab connection.** In Claude Code, you can also run `/zeroclaw:setup`.

The installer requires Node.js 22 or newer and the selected client CLI. Supported controllers are Apple Silicon macOS and ARM64/x86-64 GNU Linux with glibc 2.39 or newer. Native plugin startup needs no Node, Python, compiler, or additional download. Target operations retain the existing OpenSSH, supported GitHub CLI, and prepared Linux-account prerequisites.

For other MCP clients, configure a stdio server with command `npx` and arguments `["-y", "@zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.4", "mcp"]`. The server runs locally; a package download URL is not a hosted MCP endpoint.

## Client marketplaces

As an alternative to the installer above, add the public marketplace directly in your client:

```sh
# Codex
codex plugin marketplace add zeroclaw-labs/zeroclaw-mcp-distribution
codex plugin add zeroclaw@zeroclaw-labs

# Claude Code
claude plugin marketplace add zeroclaw-labs/zeroclaw-mcp-distribution
claude plugin install zeroclaw@zeroclaw-labs
```

Choose one installation route per client. If you already installed with `install --codex` or `install --claude`, keep using that command for updates; it owns that client's local marketplace.

## ZeroClaw and other frameworks

For a client that accepts the common MCP JSON configuration, add:

```json
{
  "mcpServers": {
    "zeroclaw": {
      "command": "npx",
      "args": ["-y", "@zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.4", "mcp"]
    }
  }
}
```

For ZeroClaw, merge a server and bundle into the client configuration, preserving existing entries:

```toml
[[mcp.servers]]
name = "zeroclaw_manager"
command = "npx"
args = ["-y", "@zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.4", "mcp"]
tool_timeout_secs = 600

[mcp_bundles.zeroclaw_manager]
servers = ["zeroclaw_manager"]
```

Include `zeroclaw_manager` in the chosen client agent's existing `mcp_bundles` list. Its tool permissions still apply. The client and the installation being managed are separate. If your client lacks MCP permission-review forms, run `npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.4 setup` in a terminal to review the connection and permissions. Terminal setup can also register an existing ZeroClaw client.

Run `npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.4 --version` once before starting a client with a short startup deadline. After acquisition, allow 20 seconds for startup and 600 seconds for management tools. Use an absolute path to `npx` if the client does not inherit your shell's PATH.

## Permissions and updates

Installing the plugin does not authorize management of a machine. Setup proposes a named connection in chat, then the client asks you to review exact permissions. Credentials stay in private local files. The plugin has no hooks or automatic tool approvals.

Run the installation command again with a later published version to update. The installer retains earlier package versions and configuration backups. An existing marketplace or MCP registration with a conflicting source is reported for review rather than silently replaced. Existing manager state remains under `~/.zeroclaw-manager/`, and the verified native runtime remains under `~/.local/lib/zeroclaw-mcp/`.

Release notes and direct downloads are available in the [distribution repository](https://github.com/zeroclaw-labs/zeroclaw-mcp-distribution). This package reuses the verified MCP runtime 0.1.0-alpha.7 and original native launchers; its own package/plugin version is 0.1.0-alpha.4.

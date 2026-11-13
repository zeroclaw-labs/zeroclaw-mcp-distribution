# ZeroClaw MCP

Your hardware. Your memories. Your choice of model.

Install the plugin for your agent:

```sh
npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.6 install --codex
# Or:
npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.6 install --claude
```

Choose both flags to install for both clients. The installer verifies the package, keeps a persistent copy outside npm's cache, backs up the affected client settings, and uses the client's plugin commands. It checks the bundled MCP without contacting a target. Restart your client and ask: **Set up ZeroClaw. Call it Home Lab and use my saved lab connection.** In Claude Code, you can also run `/zeroclaw:setup`.

The installer requires Node.js 22 or newer and the selected client CLI. Supported controllers are Apple Silicon macOS and ARM64/x86-64 GNU Linux with glibc 2.39 or newer. Native plugin startup needs no Node, Python, compiler, or additional download. Target operations retain the existing OpenSSH, supported GitHub CLI, and prepared Linux-account prerequisites.

For other MCP clients, configure a stdio server with command `npx` and arguments `["-y", "@zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.6", "mcp"]`. The server runs locally; a package download URL is not a hosted MCP endpoint.

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
      "args": ["-y", "@zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.6", "mcp"]
    }
  }
}
```

For ZeroClaw, merge a server and bundle into the client configuration, preserving existing entries:

```toml
[[mcp.servers]]
name = "zeroclaw_manager"
command = "npx"
args = ["-y", "@zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.6", "mcp"]
tool_timeout_secs = 600

[mcp_bundles.zeroclaw_manager]
servers = ["zeroclaw_manager"]
```

Include `zeroclaw_manager` in the chosen client agent's existing `mcp_bundles` list. Its tool permissions still apply. The client and the installation being managed are separate. If your client lacks MCP permission-review forms, run `npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.6 setup` in a terminal to review the connection and permissions. Terminal setup can also register an existing ZeroClaw client.

Run `npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.6 --version` once before starting a client with a short startup deadline. After acquisition, allow 20 seconds for startup and 600 seconds for management tools. Use an absolute path to `npx` if the client does not inherit your shell's PATH.

## Permissions and updates

Installing the plugin does not authorize management of a machine. Setup proposes a named connection in chat, then the client asks you to review exact permissions. Credentials stay in private local files. The plugin has no hooks or automatic tool approvals.

Run the installation command again with a later published version to update. The installer retains earlier package versions and configuration backups. An existing marketplace or MCP registration with a conflicting source is reported for review rather than silently replaced. Existing manager state remains under `~/.zeroclaw-manager/`, and the verified native runtime remains under `~/.local/lib/zeroclaw-mcp/`.

Release notes and direct downloads are available in the [distribution repository](https://github.com/zeroclaw-labs/zeroclaw-mcp-distribution). This package reuses the verified MCP runtime 0.1.0-alpha.9 and original native launchers; its own package/plugin version is 0.1.0-alpha.6.


## Automatic ZeroClaw software updates

Once an installation is manager-owned, you can opt in to the official stable
release channel. On a Mac controller:

```sh
npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.6 updates enable "Home Lab"
npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.6 updates schedule
npx -y @zeroclaw-labs/zeroclaw-mcp@0.1.0-alpha.6 updates status
```

Review the target and type `ENABLE`, then confirm the timer with `SCHEDULE`.
The native runtime stays at its persistent verified path outside npm's cache.
The timer checks hourly while the Mac is awake and the user session and SSH
connection are available. Checks and upgrades make no model calls. Ask any MCP
client to show automatic update status afterward.

New releases must pass checksum, signature, source identity and isolated
compatibility checks before the live service stops. The manager takes a bounded
backup, preserves configuration/data and restores the prior service state. It
never downgrades or automatically replays an uncertain upgrade. Unsupported
plugin migrations, layouts, release interfaces or trust-root changes stop for
operator review. This is an alpha release; an API compatibility probe cannot
prove every behavior or future migration.

To disable future checks, run the same command with
`updates disable "Home Lab"`. This waits for an admitted worker to finish and
leaves manual upgrade permissions intact. On Linux controllers use
`updates schedule-preview` for the portable `updates run` command and configure
your scheduler separately; automatic timer installation currently supports
macOS only. Fresh-install and adoption policies remain unchanged.

These commands update managed ZeroClaw software. Updating the MCP package itself
still uses the client installation command with a newer npm version.

## ZeroClaw v0.9.0 compatibility

This release supports verified installation, adoption, and upgrades for official ZeroClaw v0.9.0. Existing permissions and configuration/data protections remain in force. Verification accepts a final reply from the same session transcript when v0.9.0 returns an empty final envelope, and still requires the exact generated diagnostic marker without repeating the model call.

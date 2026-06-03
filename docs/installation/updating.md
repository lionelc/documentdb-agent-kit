# Updating the kit

New skills, rule fixes, and MCP-server updates are released on `main`. Installs do **not** auto-update — each install path has its own refresh command. Run these when you want to pull in new features or fixes:

| Install path | Update command |
|---|---|
| One-liner installer (recommended) | re-run the `install.sh` / `install.ps1` curl one-liner with the same connection string (idempotent: refreshes the kit clone, rebuilds the MCP server, and re-merges the `DocumentDB` entry into every detected client config). Pin a specific ref with `--kit-ref <ref>` and/or `--mcp-ref <ref>`. |
| Skills only (skills.sh CLI) | re-run `npx skills add Azure/documentdb-agent-kit` |

<!--
Per-agent update commands (will be uncommented once plugin install paths are published):

| Install path | Update command |
|---|---|
| Claude Code | `/plugin update documentdb@azure-documentdb` |
| Cursor | re-run `/add-plugin azure/documentdb-agent-kit` |
| Codex | `codex plugin update documentdb` |
| Gemini CLI | `gemini extensions update documentdb-agent-kit` |
| GitHub Copilot CLI | `/plugin update https://github.com/Azure/documentdb-agent-kit.git` (or uninstall + reinstall) |
-->

> **Skills CLI note:** `npx skills update` exists but is unreliable for GitHub-sourced skills on the current `skills` CLI release. **Re-running `npx skills add Azure/documentdb-agent-kit` is the recommended refresh path** — it re-fetches the latest `main` and overlays the updated rule files. Add `--all` if you originally installed with `--all`.

The MCP server is fetched via `npx -y documentdb-mcp-server` each time the agent launches the server, so MCP-server updates land automatically on the next agent restart (subject to npm cache). Skill files are snapshotted at install time and only refresh when you run one of the commands above.

To see what's changed between releases, check [`CHANGELOG.md`](../../CHANGELOG.md).

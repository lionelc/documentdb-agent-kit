# What gets installed

| Path | What |
|---|---|
| `~/.documentdb-agent-kit/agent-kit/` | Clone of this repo (skills + AGENTS.md) |
| `~/.documentdb-agent-kit/mcp-server/` | Clone + build of `microsoft/documentdb-mcp` |

Then, per detected client:

| Client | MCP entry → | Skills → |
|---|---|---|
| Claude Code | `~/.claude.json` | `~/.claude/skills/` (symlinks) |
| Claude Desktop | `claude_desktop_config.json` (per-OS path) | `Claude/skills/` (symlinks, if dir exists) |
| Cursor | `~/.cursor/mcp.json` | — (use Cursor Rules per-project) |
| GitHub Copilot CLI | `~/.copilot/mcp-config.json` | — (copy `AGENTS.md` per-project) |
| Gemini CLI | `~/.gemini/settings.json` | — (use `GEMINI.md` per-project) |

Existing entries in each client's config are preserved — the installer only
adds (or updates) a single `DocumentDB` entry. A timestamped `.bak` backup is
written before every JSON edit.

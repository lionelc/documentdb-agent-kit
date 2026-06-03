# Skills-only install (no MCP server)

To install just the skill catalog into whichever agent you're using, via the [skills.sh](https://skills.sh/) CLI:

```bash
npx skills add Azure/documentdb-agent-kit
```

This drops the rule docs into your agent's skill directory but **does not** install the MCP server. Use the [one-liner installer](../../README.md#installation) if you want the DB tools too.

> 💡 **Accept the optional `find-skills` helper when prompted.** During `npx skills add` the installer will ask whether to install [`find-skills`](https://github.com/skills-sh/find-skills) — say **yes**. It's a tiny meta-skill that lets agents auto-discover the right DocumentDB skill for a task (e.g. *"how do I create a BM25 index?"* → auto-loads `documentdb-full-text-search`) instead of relying on you to invoke skills by name. It's especially useful here because the kit ships 17 skills, more than agents reliably route on their own from `AGENTS.md` alone. If you skipped it, re-run `npx skills add find-skills` to add it later.

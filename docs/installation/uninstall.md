# Uninstall

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/Azure/documentdb-agent-kit/main/install.sh | bash -s -- --uninstall --yes
```

```powershell
# Windows
irm https://raw.githubusercontent.com/Azure/documentdb-agent-kit/main/install.ps1 -OutFile $env:TEMP\install.ps1
& $env:TEMP\install.ps1 -Uninstall -Yes
```

Removes the kit's `DocumentDB` MCP entry from every client, removes skill
symlinks, and deletes `~/.documentdb-agent-kit/`. Other MCP servers and your
non-kit skills are left untouched.

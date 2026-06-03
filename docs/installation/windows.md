# Installation — Windows

**1. Prerequisites**

Open **PowerShell** (Windows PowerShell 5.1 or pwsh 7+) — as your normal user, not admin:

```powershell
# git
winget install --id Git.Git

# Node.js 20+
winget install OpenJS.NodeJS.LTS

# Verify (open a new PowerShell window first to refresh PATH)
git --version
node --version    # must be v20.x or higher
$PSVersionTable.PSVersion   # 5.1+ or 7+
```

*(Optional but recommended)* Enable **Developer Mode** so the installer can use symlinks instead of copying files: *Settings → Privacy & security → For developers → Developer Mode = On*. Without it the installer falls back to copying — that still works, just less elegant for skill updates.

**2. Get your DocumentDB connection string** — same as [macOS](macos.md#2-get-your-documentdb-connection-string).

**3. Run the installer**

```powershell
$env:DOCUMENTDB_URI = "<paste-your-connection-string-here>"
irm https://raw.githubusercontent.com/Azure/documentdb-agent-kit/main/install.ps1 | iex
```

If you get `running scripts is disabled on this system`, run this once in the same window and re-run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**To pass flags** (`-Yes`, `-DryRun`, `-Uninstall`, etc.), `irm | iex` won't work — download then invoke:

```powershell
irm https://raw.githubusercontent.com/Azure/documentdb-agent-kit/main/install.ps1 -OutFile $env:TEMP\install.ps1
& $env:TEMP\install.ps1 -Uri "<paste-your-connection-string-here>" -Yes
```

**4. Fully quit and reopen each configured client.** Use the system tray / Task Manager — closing the window isn't enough.

**5. Verify** — see [Verify it worked](verify.md).

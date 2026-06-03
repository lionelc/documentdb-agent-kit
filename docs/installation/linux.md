# Installation — Linux

**1. Prerequisites**

```bash
# git
sudo apt install -y git           # Debian/Ubuntu
# sudo dnf install -y git         # Fedora/RHEL
# sudo pacman -S git              # Arch

# Node.js 20+ — distro packages are usually too old. Pick one:

# Option A: NodeSource (Debian/Ubuntu/Fedora/RHEL)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Option B: nvm (any distro, recommended for dev machines)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
exec $SHELL
nvm install 20 && nvm use 20

# Verify
git --version
node --version    # must be v20.x or higher
npm --version
```

**2. Get your DocumentDB connection string** — same as [macOS](macos.md#2-get-your-documentdb-connection-string).

**3. Run the installer**

```bash
curl -fsSL https://raw.githubusercontent.com/Azure/documentdb-agent-kit/main/install.sh \
  | bash -s -- --uri "<your-connection-string>" --yes
```

> The `bash -s --` part is **required** when piping through `curl` — it tells bash that everything after is an argument to the script, not to bash itself.

**4. Fully quit and reopen each configured client.** For terminal clients (Copilot CLI, Gemini CLI), exit and reopen the shell.

**5. Verify** — see [Verify it worked](verify.md).

> Don't `sudo` the installer — it only writes user-scoped configs. Running as root will create files owned by root in your home directory.

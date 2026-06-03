# Troubleshooting

| Symptom | Platform | Fix |
|---|---|---|
| `bash: line N: --uri: command not found` | macOS / Linux | Missing `bash -s --` between `curl ... \|` and the flags. |
| `running scripts is disabled on this system` | Windows | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in the same PowerShell session, then re-run. |
| `Invoke-Expression: A parameter cannot be found that matches parameter name 'ArgumentList'` | Windows | `irm \| iex` doesn't accept flags. Use the `irm -OutFile … ; & $env:TEMP\install.ps1 -Yes` pattern. |
| `npm: Unknown command: "pm"` during MCP build | Windows | Old installer bug — re-fetch the latest `install.ps1` (fixed in this kit). |
| `node: command not found` after install | all | Open a new terminal to refresh `PATH`. With nvm, also run `nvm use 20`. |
| `npm: not found` but Node.js is installed | Linux (Debian/Ubuntu) | The distro `nodejs` package sometimes omits npm — `sudo apt install -y npm`, or use nvm. |
| `symlink failed for <skill>; copying instead` warnings | Windows | Harmless. Enable Developer Mode if you want real symlinks. |
| Agent: `connection_profile "default" not found` | all | Tell the agent to use profile `default` explicitly, or pass `--profile <name>` / `-Profile <name>` to the installer. |
| Agent: `AUTH_REQUIRED is true ...` or server exits at launch | all | Re-run the installer — it sets `AUTH_REQUIRED=false` + `TRUST_LOCAL_STDIO=true`, required for local stdio. This only disables the MCP-server's Entra-JWT *transport* gate; your cluster's SCRAM/Entra auth is unaffected. |
| TLS error against Azure | all | Confirm `tls=true` is in the URI and the password is URL-encoded. |
| Connection timeout to Azure | all | Azure portal → cluster → *Networking* → add your client IP to the firewall allowlist. |
| `Permission denied` writing into `~/.claude.json` | Linux / macOS | Don't `sudo` the installer — it writes user-scoped configs. Run as your normal user. |

# 🏠 Home Server AI

**One command to set up your personal cloud.**

AI-powered home server setup that just works. No technical knowledge required.

---

## ⚡ Quick Start (2 Minutes)

```bash
# 1. Install
curl -fsSL https://yourdomain.com/install.sh | bash

# 2. Run setup
home-server setup

# 3. Answer a few questions
# 4. Wait 15 minutes
# 5. Done! Access your services
```

---

## 🎯 What You Get

| Service | What It Does | Access After Setup |
|---------|--------------|-------------------|
| **Tailscale** | Secure VPN to your server | `tailscale status` |
| **AdGuard** | Block ads on all devices | `http://your-server:3000` |
| **Jellyfin** | Your personal Netflix | `http://your-server:8096` |
| **Immich** | Photo backup (Google Photos alternative) | `http://your-server:2283` |
| **OpenClaw** | AI assistant for your server | Built-in |

---

## 🚀 All Commands

```bash
# Setup
home-server setup              # Interactive setup
home-server setup --web        # Use web browser for config
home-server setup --dry-run    # Preview what will happen

# Monitor
home-server status             # Quick status check
home-server dashboard          # Start web dashboard (port 8081)

# Manage
home-server updates            # Check for updates
home-server updates --update jellyfin  # Update a service
home-server rollback --create  # Create backup point
home-server rollback --list    # See available backups
```

---

## ✨ Why This Is Better

| Feature | Others | Home Server AI |
|---------|--------|----------------|
| **Setup Time** | 2-4 hours | **15 minutes** |
| **Failure Recovery** | Start over | **Resume where you left off** |
| **Updates** | Manual check | **Automatic notifications** |
| **Rollback** | None | **One command undo** |
| **Monitoring** | SSH + commands | **Beautiful web dashboard** |
| **AI Help** | None | **GPT-4/Claude assistance** |

---

## 🛡️ Safety Features

- ✅ **Pre-flight Checks**: Validates your system before changing anything
- ✅ **Dry Run Mode**: Preview all changes before executing
- ✅ **Automatic Backups**: Create restore points with one command
- ✅ **Smart Error Recovery**: AI suggests fixes when things go wrong
- ✅ **Command Validation**: Dangerous commands are blocked

---

## 📋 Requirements

- Ubuntu 22.04+, Debian 12+, or Raspberry Pi OS
- 4GB+ RAM
- 20GB+ free disk space
- Internet connection

**Optional**: OpenAI API key for AI-powered planning (falls back to smart templates if not provided)

---

## 🎓 Example Session

```
$ home-server setup

🏠 Home Server AI Setup Agent
========================================

📊 Step 1: Detecting hardware...
   CPU: Intel i5-8400 (6 cores)
   RAM: 16.0 GB
   Disk: 450 GB available

📝 Step 2: Gathering requirements...
What do you want to use your home server for?
  1. File storage & backup
  2. Media server (movies, TV, music)
  3. Network-wide ad blocking
  4. Secure remote access (VPN)

Your choices: 1,2,3,4

🧠 Step 3: Generating installation plan...
   ✓ Plan: Home Server Installation Plan
   ✓ Steps: 12
   ✓ Est. time: 15 minutes

🚀 Step 4: Executing installation plan...
   [████████████████████░░░░░░░░░░░░░░░░░░] 6/12 (50%)

🎉 All steps completed successfully!

✓ Your home server is ready!

📋 Access your services:
   • AdGuard Home: http://localhost:3000
   • Jellyfin: http://localhost:8096
   • Tailscale: Run 'tailscale status'

💾 Session saved: a1b2c3d4
```

---

## 🔧 Troubleshooting

```bash
# Something went wrong?
home-server rollback --list          # See backups
home-server rollback --rollback X    # Restore to backup X

# Check status
home-server status
home-server dashboard

# View logs
home-server dashboard  # Then click "Logs" for any service
```

---

## 📖 Full Documentation

- [README.md](README.md) - Complete documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [FIXES_SUMMARY.md](FIXES_SUMMARY.md) - Issues we prevent

---

**Built with ❤️ for the self-hosting community**

MIT License | [GitHub](https://github.com/yourusername/home-server-agent)

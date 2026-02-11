# 🏠 Home Server AI Setup Agent

An AI-powered agent that automatically sets up a home server stack on Linux. Designed for non-technical users who want their own home server without the complexity.

## ✨ What Makes This Different

Unlike other installers, this uses **AI to adapt to your specific hardware and needs**:

- **🤖 AI Planning**: GPT-4/Claude analyzes your hardware and creates a custom installation plan
- **🔍 Pre-flight Checks**: Validates your system before making any changes (no more broken installs!)
- **🛡️ Smart Error Recovery**: When things fail, the AI suggests fixes and can auto-retry
- **📊 Real-time Monitoring**: Beautiful web dashboard shows service status and system metrics
- **🔄 Rollback Capability**: Undo installations if something goes wrong
- **📦 Update Checker**: Keep all your services up to date with one command
- **💾 Resume Capability**: Interrupted setup? Resume exactly where you left off

## 🚀 Quick Start

### Prerequisites

- Linux system (Ubuntu 22.04+, Debian 12+, Linux Mint 21+, Raspberry Pi OS)
- Python 3.11+
- Internet connection
- OpenAI API key (optional - falls back to smart templates)

### One-Line Install

```bash
curl -fsSL https://yourdomain.com/install.sh | bash
home-server-setup
```

### Manual Install

```bash
git clone https://github.com/yourusername/home-server-agent.git
cd home-server-agent
pip3 install -r requirements.txt

# Optional: Set OpenAI API key for AI-powered planning
export OPENAI_API_KEY="sk-..."

# Run setup
python3 main.py
```

## 📖 Usage Options

```bash
# Interactive CLI setup (recommended for first run)
python3 main.py

# Web configuration interface
python3 main.py --web
# Then open http://localhost:8080

# Use existing config file
python3 main.py --config my-config.json

# Dry run - see what would happen without executing
python3 main.py --dry-run

# Auto-approve all steps (unattended mode)
python3 main.py --yes

# Resume failed session
python3 main.py --resume abc123

# View session dashboard
python3 dashboard.py

# Start monitoring dashboard (after setup)
python3 monitoring_dashboard.py

# Check for updates
python3 update_checker.py

# Create rollback point
python3 rollback_manager.py --create
```

## 🎯 What Gets Installed

| Component | Purpose | License | Why It's Included |
|-----------|---------|---------|-------------------|
| **Tailscale** | Secure mesh VPN | BSD-3 | Zero-config networking, no port forwarding |
| **AdGuard Home** | Network ad blocker | GPL v3 | Block ads on all devices without browser extensions |
| **OpenClaw** | AI agent framework | Apache 2.0 | Your personal AI assistant for the server |
| **Jellyfin** (opt) | Media server | GPL v2 | Netflix-like experience for your movies |
| **Immich** (opt) | Photo backup | AGPL v3 | Google Photos alternative, keeps your privacy |

## 🖥️ Monitoring Dashboard

After installation, start the monitoring dashboard to see real-time status:

```bash
# Start web dashboard
python3 monitoring_dashboard.py
# Open http://localhost:8081

# Or check status from CLI
python3 monitoring_dashboard.py --cli
```

### Dashboard Features

- **System Metrics**: CPU, RAM, disk usage with visual gauges
- **Service Status**: Real-time health of all installed services
- **Service Controls**: Start, stop, and restart services from the UI
- **Log Viewer**: View logs for each service without SSH
- **Auto-refresh**: Updates every 5 seconds automatically

![Dashboard Preview](docs/dashboard-preview.png)

## 🔄 Rollback & Backup

Made a mistake? No problem! Create rollback points before major changes:

```bash
# Create a rollback point
python3 rollback_manager.py --create --description "Before updating Jellyfin"

# List available rollback points
python3 rollback_manager.py --list

# Rollback to a specific point
python3 rollback_manager.py --rollback backup_20250210_143022

# Delete old rollback points
python3 rollback_manager.py --delete backup_20250210_143022
```

## 📦 Update Checker

Keep your services up to date:

```bash
# Check for updates
python3 update_checker.py

# Check specific service
python3 update_checker.py --update jellyfin --dry-run

# Update a service
python3 update_checker.py --update jellyfin

# Output as JSON for automation
python3 update_checker.py --json
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│  User runs: python main.py              │
└──────────────┬──────────────────────────┘
               │
    ┌──────────▼──────────┐
    │  Pre-flight Checks  │  ← Validates system readiness
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  Hardware Detection │  ← Analyzes CPU, RAM, disk, distro
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  User Interview     │  ← CLI or Web UI, gathers requirements
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  AI Planning Engine │  ← GPT-4 creates custom installation plan
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  Safe Execution     │  ← Runs commands, validates, recovers
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  Progress Tracking  │  ← SQLite state, resume capability
    └─────────────────────┘
               │
    ┌──────────▼──────────┐
    │  Monitoring Dash    │  ← Real-time service monitoring
    └─────────────────────┘
```

## 💾 Session Management

Every setup creates a session that can be resumed:

```bash
# View all sessions
python3 dashboard.py

# See details of specific session
python3 dashboard.py abc123

# Resume a session
python3 main.py --resume abc123
```

Sessions are stored in `state.db` (SQLite) with full execution history.

## 🔒 Safety Features

- **Pre-flight Validation**: Checks system readiness before making changes
- **Command Validation**: Blocks dangerous commands (`rm -rf /`, etc.)
- **Dry Run Mode**: Preview all commands before execution
- **Step-by-Step**: Each step verified before proceeding
- **Automatic Backups**: Rollback commands for each step
- **Sudo Confirmation**: Prompts before privileged operations
- **Path Traversal Protection**: Sanitizes all user paths

## 🐛 Troubleshooting

### OpenAI API Issues
If GPT-4 planning fails, the system automatically falls back to template plans:
```bash
# Set your API key
export OPENAI_API_KEY="sk-..."

# Or run without (uses templates)
python3 main.py
```

### Permission Errors
```bash
# Ensure you have sudo access
sudo -v

# Or run steps manually with sudo when prompted
```

### Port Conflicts (AdGuard)
AdGuard Home uses port 53 which may conflict with systemd-resolved:
```bash
# The setup handles this automatically, but if needed:
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved
```

### Docker Permission Issues
```bash
# If you get 'permission denied' for docker:
sudo usermod -aG docker $USER
newgrp docker
# Or log out and back in
```

### Service Won't Start
```bash
# Check service logs
python3 monitoring_dashboard.py --cli

# Or view logs for specific service
python3 monitoring_dashboard.py
# Then click "Logs" button for the service
```

### Rollback Issues
```bash
# Check available rollback points
python3 rollback_manager.py --list

# Rollback to a known good state
python3 rollback_manager.py --rollback backup_20250210_143022
```

## 📊 Example Output

```
🏠 Home Server AI Setup Agent
========================================
Session ID: a1b2c3d4

🔍 Pre-flight System Checks
==================================================
  ✓ Python Version: Python 3.11.4 ✓
  ✓ Root Disk Space: 45.2GB free on root ✓
  ✓ Storage Path Space: 892.1GB free at /mnt/storage ✓
  ✓ Internet Connectivity: Internet connection OK ✓
  ⚠️ Port Availability: Port 53 may be in use (systemd-resolved)
     💡 AdGuard setup will handle this automatically
  ✓ System RAM: 16.0GB RAM ✓
  ✓ CPU Cores: 8 cores ✓
  ✓ Sudo Access: Passwordless sudo available ✓
  ✓ Docker: Docker installed and running ✓
  ✓ Systemd: Systemd available ✓
--------------------------------------------------
  Passed: 9, Warnings: 1, Errors: 0

📊 Step 1: Detecting hardware...
   CPU: Intel(R) Core(TM) i5-8400 (6 cores)
   RAM: 16.0 GB
   Disk: {'/': 450.5}
   OS: ubuntu 22.04

📝 Step 2: Gathering requirements...
   Selected: ['vpn', 'ad_blocking', 'media_server']

🧠 Step 3: Generating installation plan...
   ✓ Plan: Home Server Installation Plan
   ✓ Steps: 12
   ✓ Est. time: 15 minutes

🚀 Step 4: Executing installation plan...
   [████████████████████░░░░░░░░░░░░░░░░░░] 6/12 (50%)
```

## 🛠️ Development

```bash
# Run tests
make test

# Dry run to see what would happen
make dry-run

# Clean up generated files
make clean

# Check code style
make lint
```

## 📁 Project Structure

```
home-server-agent/
├── main.py                 # Entry point with CLI
├── hardware_detector.py    # System detection
├── interview.py            # CLI user interview
├── planner.py              # GPT-4 / Template planning
├── executor.py             # Safe command execution
├── error_recovery.py       # AI-powered error fixing
├── preflight.py            # Pre-installation validation
├── monitoring_dashboard.py # Real-time monitoring web UI
├── rollback_manager.py     # Backup and rollback functionality
├── update_checker.py       # Service update checking
├── config_validator.py     # Configuration validation
├── ai_provider.py          # Multi-provider AI support
├── retry_utils.py          # Retry logic with backoff
├── web_config.py           # Flask web interface
├── dashboard.py            # Session status viewer
├── state.db                # SQLite progress tracking
├── config.json             # Generated configuration
├── requirements.txt        # Python dependencies
├── install.sh              # One-line installer
├── Makefile                # Convenience commands
├── tests/                  # Test suite
├── README.md              # This file
└── COMPETITION_ANALYSIS.md # Competitive analysis
```

## 📝 Configuration File Format

Create a `config.json` for automated setups:

```json
{
  "use_cases": ["vpn", "ad_blocking", "media_server"],
  "media_types": ["movies", "tv", "photos"],
  "want_tailscale": true,
  "want_adguard": true,
  "want_openclaw": true,
  "want_immich": true,
  "want_jellyfin": true,
  "storage_path": "/mnt/storage",
  "tailscale_auth_key": "tskey-auth-...",
  "openclaw_gateway_token": "ocgw-...",
  "admin_email": "admin@example.com",
  "ai_provider": "openai",
  "ai_model": "gpt-4o-mini",
  "ai_api_key": "sk-..."
}
```

## 🎯 Competition Analysis

See [COMPETITION_ANALYSIS.md](COMPETITION_ANALYSIS.md) for detailed comparison with:
- CasaOS
- Umbrel
- TrueNAS Scale
- OpenMediaVault
- Proxmox

Key differentiators:
- ✅ Pre-flight compatibility checks (others lack this)
- ✅ AI-powered planning and error recovery
- ✅ Rollback capability
- ✅ Real-time monitoring dashboard
- ✅ Update checker for all services
- ✅ Multi-provider AI support (OpenAI, Anthropic, Ollama)

## 📜 License

This project is MIT licensed. The installed components have their own licenses:
- Tailscale: BSD-3
- AdGuard Home: GPL v3
- OpenClaw: Apache 2.0
- Jellyfin: GPL v2
- Immich: AGPL v3

## 🤝 Support

For issues or questions:
1. Check logs in `setup.log`
2. Run `python3 dashboard.py` to see session status
3. Resume failed session: `python3 main.py --resume <session_id>`
4. Check monitoring dashboard: `python3 monitoring_dashboard.py --cli`
5. Create rollback point before trying again: `python3 rollback_manager.py --create`

---

Built with ❤️ for the self-hosting community.

#!/bin/bash
# Home Server AI - Installation Script
# Simple, reliable installation

set -e

echo "🏠 Home Server AI - Installer"
echo "=============================="
echo

# Check Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ Linux required"
    exit 1
fi

# Check Python 3.11+
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
if [ "$(printf '%s\n' "3.11" "$PYTHON_VERSION" | sort -V | head -n1)" != "3.11" ]; then 
    echo "❌ Python 3.11+ required, found $PYTHON_VERSION"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION"

# Install pip if needed
if ! command -v pip3 &> /dev/null; then
    echo "📦 Installing pip..."
    sudo apt update && sudo apt install -y python3-pip
fi

# Install directory
INSTALL_DIR="$HOME/.local/share/home-server"
mkdir -p "$INSTALL_DIR"

# Download latest release
echo "📥 Downloading..."
if [ -d ".git" ]; then
    # Development mode - copy current directory
    cp -r . "$INSTALL_DIR/"
else
    # Production - download from GitHub
    curl -fsSL "https://github.com/yourusername/home-server-ai/archive/main.tar.gz" | \
        tar -xz -C "$INSTALL_DIR" --strip-components=1 2>/dev/null || \
        echo "⚠️  Could not download, using local files"
    cp -r . "$INSTALL_DIR/" 2>/dev/null || true
fi

# Install dependencies
echo "📦 Installing dependencies..."
cd "$INSTALL_DIR"
pip3 install --user -q -r requirements.txt

# Create unified CLI
cat > "$HOME/.local/bin/home-server" << 'EOF'
#!/bin/bash
export PYTHONPATH="$HOME/.local/share/home-server:$PYTHONPATH"
python3 "$HOME/.local/share/home-server/home-server" "$@"
EOF
chmod +x "$HOME/.local/bin/home-server"

# Add to PATH if needed
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    export PATH="$HOME/.local/bin:$PATH"
fi

echo
echo "✅ Installation complete!"
echo
echo "Quick start:"
echo "  home-server setup       # Run setup"
echo "  home-server status      # Check status"
echo "  home-server --help      # See all commands"
echo

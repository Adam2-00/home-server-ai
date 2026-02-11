#!/bin/bash
# Deploy website to a static hosting service

echo "🌐 Home Server AI Website Deployment"
echo "====================================="
echo

# Check if we have the website files
if [ ! -f "index.html" ]; then
    echo "❌ index.html not found in current directory"
    echo "   Run this from the home-server-website directory"
    exit 1
fi

echo "✓ Found index.html"

# Option 1: Deploy to GitHub Pages
echo
echo "Option 1: GitHub Pages (Free)"
echo "------------------------------"
echo "1. Create a GitHub repository"
echo "2. Push these files to the repo"
echo "3. Enable GitHub Pages in repo settings"
echo "4. Your site will be at: https://yourusername.github.io/repo-name"
echo

# Option 2: Deploy to Netlify
echo "Option 2: Netlify (Free)"
echo "-------------------------"
echo "1. Go to https://app.netlify.com/drop"
echo "2. Drag and drop this folder"
echo "3. Get instant HTTPS hosting"
echo

# Option 3: Deploy to Cloudflare Pages
echo "Option 3: Cloudflare Pages (Free)"
echo "----------------------------------"
echo "1. Go to https://pages.cloudflare.com"
echo "2. Connect your GitHub repo or upload directly"
echo "3. Get global CDN hosting"
echo

# Option 4: Simple Python server (for testing)
echo "Option 4: Local Testing"
echo "------------------------"
echo "Run: python3 -m http.server 8080"
echo "Then open: http://localhost:8080"
echo

# Create _redirects file for Netlify
if [ ! -f "_redirects" ]; then
    echo "/install.sh https://raw.githubusercontent.com/yourusername/home-server-agent/main/install.sh 301" > _redirects
    echo "✓ Created _redirects file for Netlify"
fi

# Create a simple README for the website
cat > README.md << 'EOF'
# Home Server AI Website

This is the marketing website for the Home Server AI Setup Agent.

## Quick Start

```bash
# Local development
python3 -m http.server 8080

# Open http://localhost:8080
```

## Deployment

### Netlify (Recommended - Free)
1. Go to https://app.netlify.com/drop
2. Drag and drop this folder
3. Site is live instantly with HTTPS

### GitHub Pages (Free)
1. Push to GitHub repository
2. Enable GitHub Pages in settings
3. Site deploys automatically

### Cloudflare Pages (Free)
1. Connect repo at https://pages.cloudflare.com
2. Or upload directly
3. Global CDN hosting

## Custom Domain

To use a custom domain (e.g., homeserver.ai):

1. Buy domain from Namecheap, Cloudflare, etc.
2. Add domain in your hosting provider
3. Update DNS records as instructed
4. Wait for SSL certificate provisioning

## Analytics

Add analytics to track visitors:
- Plausible (privacy-friendly, paid)
- Fathom (privacy-friendly, paid)
- Google Analytics (free, less privacy)
- Cloudflare Web Analytics (free)

Just add the tracking code before </head> in index.html.
EOF

echo "✓ Created README.md"
echo
echo "🎉 Website ready for deployment!"
echo "   Preview locally: python3 -m http.server 8080"

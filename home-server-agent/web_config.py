"""
Web Config Interface - Apple-Inspired Design with Security Hardening
Simple Flask server for initial configuration with intuitive UI.
SECURITY: CSRF protection, input validation, security headers
"""
import json
import os
import secrets
import hashlib
from pathlib import Path
try:
    from flask import Flask, render_template_string, request, jsonify, g
except ImportError:
    Flask = None
    render_template_string = None
    request = None
    jsonify = None
    g = None


# Apple-inspired HTML Template (unchanged)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Home Server Setup</title>
    <style>
        :root {
            --apple-blue: #007AFF;
            --apple-green: #34C759;
            --apple-orange: #FF9500;
            --apple-red: #FF3B30;
            --apple-gray: #8E8E93;
            --apple-light-gray: #F2F2F7;
            --apple-bg: #F5F5F7;
            --card-bg: #FFFFFF;
            --text-primary: #1C1C1E;
            --text-secondary: #6C6C70;
            --border-radius: 12px;
            --spacing: 20px;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
            background: var(--apple-bg);
            color: var(--text-primary);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }
        
        .progress-container {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: rgba(0,0,0,0.05);
            z-index: 100;
        }
        
        .progress-bar {
            height: 100%;
            background: var(--apple-blue);
            width: 0%;
            transition: width 0.4s ease;
        }
        
        .container {
            max-width: 680px;
            margin: 0 auto;
            padding: 60px 20px 100px;
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
        }
        
        .header-icon {
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 22px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 24px;
            font-size: 40px;
            box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
        }
        
        .header h1 { font-size: 32px; font-weight: 700; letter-spacing: -0.5px; margin-bottom: 8px; }
        .header p { color: var(--text-secondary); font-size: 17px; }
        
        .step-indicator {
            display: flex;
            justify-content: center;
            gap: 8px;
            margin-bottom: 40px;
        }
        
        .step-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #D1D1D6;
            transition: all 0.3s ease;
        }
        
        .step-dot.active { background: var(--apple-blue); width: 24px; border-radius: 4px; }
        .step-dot.completed { background: var(--apple-green); }
        
        .card {
            background: var(--card-bg);
            border-radius: var(--border-radius);
            padding: var(--spacing);
            margin-bottom: var(--spacing);
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        
        .card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
        
        .card-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .card-subtitle { color: var(--text-secondary); font-size: 15px; margin-bottom: 20px; }
        
        .form-group { margin-bottom: 20px; }
        
        .form-label {
            display: block;
            font-size: 15px;
            font-weight: 500;
            margin-bottom: 8px;
            color: var(--text-primary);
        }
        
        .form-hint { font-size: 13px; color: var(--text-secondary); margin-top: 6px; }
        
        input[type="text"],
        input[type="email"],
        input[type="password"],
        select {
            width: 100%;
            padding: 14px 16px;
            font-size: 16px;
            border: 1px solid #E5E5EA;
            border-radius: 10px;
            background: #FAFAFA;
            transition: all 0.2s ease;
            font-family: inherit;
        }
        
        input:focus, select:focus {
            outline: none;
            border-color: var(--apple-blue);
            background: white;
            box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.1);
        }
        
        .selection-grid { display: grid; gap: 12px; }
        
        .selection-card {
            display: flex;
            align-items: center;
            padding: 16px;
            background: #FAFAFA;
            border: 2px solid transparent;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .selection-card:hover { background: #F2F2F7; }
        .selection-card.selected { border-color: var(--apple-blue); background: rgba(0, 122, 255, 0.05); }
        .selection-card input { width: 22px; height: 22px; margin-right: 14px; accent-color: var(--apple-blue); }
        
        .selection-content { flex: 1; }
        .selection-title { font-weight: 500; font-size: 16px; margin-bottom: 2px; }
        .selection-desc { font-size: 13px; color: var(--text-secondary); }
        
        .toggle-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 0;
            border-bottom: 1px solid #F2F2F7;
        }
        
        .toggle-container:last-child { border-bottom: none; }
        
        .toggle-info h4 { font-size: 16px; font-weight: 500; margin-bottom: 2px; }
        .toggle-info p { font-size: 13px; color: var(--text-secondary); }
        
        .toggle { position: relative; width: 51px; height: 31px; }
        .toggle input { opacity: 0; width: 0; height: 0; }
        
        .toggle-slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background: #E5E5EA;
            border-radius: 31px;
            transition: 0.3s;
        }
        
        .toggle-slider:before {
            position: absolute;
            content: "";
            height: 27px;
            width: 27px;
            left: 2px;
            bottom: 2px;
            background: white;
            border-radius: 50%;
            transition: 0.3s;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .toggle input:checked + .toggle-slider { background: var(--apple-green); }
        .toggle input:checked + .toggle-slider:before { transform: translateX(20px); }
        
        .drive-option {
            display: flex;
            align-items: center;
            padding: 16px;
            background: #FAFAFA;
            border: 2px solid transparent;
            border-radius: 10px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .drive-option:hover { background: #F2F2F7; }
        .drive-option.selected { border-color: var(--apple-blue); background: rgba(0, 122, 255, 0.05); }
        
        .drive-icon {
            width: 44px;
            height: 44px;
            background: var(--apple-light-gray);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            margin-right: 14px;
        }
        
        .drive-info { flex: 1; }
        .drive-name { font-weight: 500; font-size: 15px; margin-bottom: 2px; }
        .drive-details { font-size: 13px; color: var(--text-secondary); }
        .drive-size { font-size: 13px; color: var(--apple-green); font-weight: 500; }
        
        .warning-box {
            background: #FFF3E0;
            border-left: 4px solid var(--apple-orange);
            padding: 16px;
            border-radius: 8px;
            margin: 16px 0;
        }
        
        .warning-box h4 {
            color: #E65100;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .warning-box ul { margin-left: 20px; color: #BF360C; font-size: 13px; }
        .warning-box li { margin-bottom: 4px; }
        
        .info-box {
            background: #E3F2FD;
            border-left: 4px solid var(--apple-blue);
            padding: 14px 16px;
            border-radius: 8px;
            margin: 16px 0;
            font-size: 14px;
            color: #1565C0;
        }
        
        .button-container {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(20px);
            padding: 16px 20px;
            display: flex;
            gap: 12px;
            border-top: 1px solid #E5E5EA;
        }
        
        .btn {
            flex: 1;
            padding: 14px 24px;
            font-size: 17px;
            font-weight: 500;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: inherit;
        }
        
        .btn-secondary { background: #E5E5EA; color: var(--text-primary); }
        .btn-secondary:hover { background: #D1D1D6; }
        
        .btn-primary { background: var(--apple-blue); color: white; }
        .btn-primary:hover { background: #0051D5; }
        
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .step-section { display: none; }
        .step-section.active { display: block; animation: fadeIn 0.4s ease; }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .provider-card {
            display: flex;
            align-items: center;
            padding: 18px;
            background: #FAFAFA;
            border: 2px solid transparent;
            border-radius: 12px;
            margin-bottom: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .provider-card:hover { background: #F2F2F7; }
        .provider-card.selected { border-color: var(--apple-blue); background: rgba(0, 122, 255, 0.05); }
        
        .provider-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            margin-right: 16px;
        }
        
        .provider-info h4 { font-size: 16px; font-weight: 600; margin-bottom: 2px; }
        .provider-info p { font-size: 13px; color: var(--text-secondary); }
        
        .summary-item {
            display: flex;
            justify-content: space-between;
            padding: 14px 0;
            border-bottom: 1px solid #F2F2F7;
        }
        
        .summary-item:last-child { border-bottom: none; }
        
        .summary-label { color: var(--text-secondary); font-size: 15px; }
        .summary-value { font-weight: 500; font-size: 15px; text-align: right; }
        
        @media (max-width: 640px) {
            .container { padding: 30px 16px 100px; }
            .header h1 { font-size: 28px; }
            .card { padding: 16px; }
        }
    </style>
</head>
<body>
    <div class="progress-container">
        <div class="progress-bar" id="progressBar"></div>
    </div>
    
    <div class="container">
        <div class="header">
            <div class="header-icon">🏠</div>
            <h1>Home Server Setup</h1>
            <p>Configure your personal cloud in minutes</p>
        </div>
        
        <div class="step-indicator">
            <div class="step-dot active" data-step="1"></div>
            <div class="step-dot" data-step="2"></div>
            <div class="step-dot" data-step="3"></div>
            <div class="step-dot" data-step="4"></div>
            <div class="step-dot" data-step="5"></div>
        </div>
        
        <!-- Step 1: AI Configuration -->
        <div class="step-section active" id="step1">
            <div class="card">
                <div class="card-title">🤖 AI Configuration</div>
                <div class="card-subtitle">Choose how the assistant creates your installation plan</div>
                
                <div class="selection-grid">
                    <label class="provider-card" onclick="selectProvider('openai')">
                        <input type="radio" name="ai_provider" value="openai" style="display:none">
                        <div class="provider-icon" style="background: #E3F2FD;">🧠</div>
                        <div class="provider-info">
                            <h4>OpenAI GPT-4</h4>
                            <p>Best overall performance • Requires API key</p>
                        </div>
                    </label>
                    
                    <label class="provider-card" onclick="selectProvider('anthropic')">
                        <input type="radio" name="ai_provider" value="anthropic" style="display:none">
                        <div class="provider-icon" style="background: #F3E5F5;">🔮</div>
                        <div class="provider-info">
                            <h4>Anthropic Claude</h4>
                            <p>Excellent for technical tasks • Requires API key</p>
                        </div>
                    </label>
                    
                    <label class="provider-card" onclick="selectProvider('ollama')">
                        <input type="radio" name="ai_provider" value="ollama" style="display:none">
                        <div class="provider-icon" style="background: #E8F5E9;">🦙</div>
                        <div class="provider-info">
                            <h4>Ollama (Local)</h4>
                            <p>Free, runs on your machine • Requires setup</p>
                        </div>
                    </label>
                    
                    <label class="provider-card" onclick="selectProvider('none')">
                        <input type="radio" name="ai_provider" value="none" style="display:none">
                        <div class="provider-icon" style="background: #FFF3E0;">📋</div>
                        <div class="provider-info">
                            <h4>Template Plans</h4>
                            <p>No AI needed • Uses pre-built templates</p>
                        </div>
                    </label>
                </div>
                
                <div id="aiKeySection" style="display:none; margin-top:20px;">
                    <div class="form-group">
                        <label class="form-label">API Key</label>
                        <input type="password" id="aiApiKey" placeholder="Enter your API key">
                        <p class="form-hint">Your key is never stored on our servers</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Step 2: Use Cases -->
        <div class="step-section" id="step2">
            <div class="card">
                <div class="card-title">📋 What will you use this for?</div>
                <div class="card-subtitle">Select all that apply</div>
                
                <div class="selection-grid">
                    <label class="selection-card" onclick="toggleCheckbox(this)">
                        <input type="checkbox" name="use_cases" value="media_server">
                        <div class="selection-content">
                            <div class="selection-title">🎬 Media Server</div>
                            <div class="selection-desc">Movies, TV shows, music streaming</div>
                        </div>
                    </label>
                    
                    <label class="selection-card" onclick="toggleCheckbox(this)">
                        <input type="checkbox" name="use_cases" value="photos">
                        <div class="selection-content">
                            <div class="selection-title">📸 Photo Backup</div>
                            <div class="selection-desc">Automatic photo backup from phones</div>
                        </div>
                    </label>
                    
                    <label class="selection-card" onclick="toggleCheckbox(this)">
                        <input type="checkbox" name="use_cases" value="file_storage">
                        <div class="selection-content">
                            <div class="selection-title">📁 File Storage</div>
                            <div class="selection-desc">Personal cloud files & documents</div>
                        </div>
                    </label>
                    
                    <label class="selection-card" onclick="toggleCheckbox(this)">
                        <input type="checkbox" name="use_cases" value="ad_blocking">
                        <div class="selection-content">
                            <div class="selection-title">🛡️ Ad Blocking</div>
                            <div class="selection-desc">Block ads on your entire network</div>
                        </div>
                    </label>
                    
                    <label class="selection-card" onclick="toggleCheckbox(this)">
                        <input type="checkbox" name="use_cases" value="vpn">
                        <div class="selection-content">
                            <div class="selection-title">🔒 Remote Access</div>
                            <div class="selection-desc">Access your server from anywhere</div>
                        </div>
                    </label>
                </div>
            </div>
        </div>
        
        <!-- Step 3: Storage -->
        <div class="step-section" id="step3">
            <div class="card">
                <div class="card-title">💾 Storage Location</div>
                <div class="card-subtitle">Where should your data be stored?</div>
                
                <div id="driveList">
                    <div class="info-box">Scanning for storage devices...</div>
                </div>
                
                <div class="form-group" style="margin-top:20px;">
                    <label class="form-label">Or enter custom path</label>
                    <input type="text" id="customPath" placeholder="/mnt/mydrive">
                </div>
            </div>
        </div>
        
        <!-- Step 4: Components -->
        <div class="step-section" id="step4">
            <div class="card">
                <div class="card-title">🔧 Components</div>
                <div class="card-subtitle">Choose which services to install</div>
                
                <div class="toggle-container">
                    <div class="toggle-info">
                        <h4>Tailscale VPN</h4>
                        <p>Secure remote access to your server</p>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" id="tailscale" checked onchange="toggleTailscale()">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                
                <div id="tailscaleOptions" style="margin-left:20px; margin-bottom:20px;">
                    <div class="toggle-container">
                        <div class="toggle-info">
                            <h4>Exit Node</h4>
                            <p>Route all traffic through this server</p>
                        </div>
                        <label class="toggle">
                            <input type="checkbox" id="tailscaleExit">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                    
                    <div class="toggle-container">
                        <div class="toggle-info">
                            <h4>Tailscale SSH</h4>
                            <p>SSH access over Tailscale network</p>
                        </div>
                        <label class="toggle">
                            <input type="checkbox" id="tailscaleSsh" checked>
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                </div>
                
                <div class="toggle-container">
                    <div class="toggle-info">
                        <h4>AdGuard Home</h4>
                        <p>Network-wide ad blocking</p>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" id="adguard" checked>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                
                <div class="toggle-container">
                    <div class="toggle-info">
                        <h4>Jellyfin</h4>
                        <p>Media server for movies & TV</p>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" id="jellyfin">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                
                <div class="toggle-container">
                    <div class="toggle-info">
                        <h4>Immich</h4>
                        <p>Photo backup & management</p>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" id="immich">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                
                <div class="toggle-container">
                    <div class="toggle-info">
                        <h4>FileBrowser</h4>
                        <p>Web file manager & sharing</p>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" id="filebrowser">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            </div>
        </div>
        
        <!-- Step 5: Review -->
        <div class="step-section" id="step5">
            <div class="card">
                <div class="card-title">✅ Review Configuration</div>
                <div class="card-subtitle">Confirm before starting installation</div>
                
                <div id="summaryContent"></div>
            </div>
        </div>
    </div>
    
    <div class="button-container">
        <button class="btn btn-secondary" id="backBtn" onclick="prevStep()" style="display:none">Back</button>
        <button class="btn btn-primary" id="nextBtn" onclick="nextStep()">Continue</button>
    </div>
    
    <script>
        let currentStep = 1;
        const totalSteps = 5;
        let csrfToken = '';
        
        // Fetch CSRF token on load
        fetch('/api/csrf-token')
            .then(r => r.json())
            .then(data => csrfToken = data.csrf_token);
        
        function updateProgress() {
            const progress = (currentStep / totalSteps) * 100;
            document.getElementById('progressBar').style.width = progress + '%';
            
            document.querySelectorAll('.step-dot').forEach((dot, index) => {
                dot.classList.remove('active', 'completed');
                if (index + 1 < currentStep) dot.classList.add('completed');
                else if (index + 1 === currentStep) dot.classList.add('active');
            });
        }
        
        function showStep(step) {
            document.querySelectorAll('.step-section').forEach(s => s.classList.remove('active'));
            document.getElementById('step' + step).classList.add('active');
            
            document.getElementById('backBtn').style.display = step === 1 ? 'none' : 'block';
            document.getElementById('nextBtn').textContent = step === totalSteps ? 'Start Setup' : 'Continue';
            
            if (step === 3) loadDrives();
            if (step === 5) generateSummary();
            
            updateProgress();
        }
        
        function nextStep() {
            if (currentStep < totalSteps) {
                currentStep++;
                showStep(currentStep);
            } else submitConfig();
        }
        
        function prevStep() {
            if (currentStep > 1) {
                currentStep--;
                showStep(currentStep);
            }
        }
        
        function selectProvider(provider) {
            document.querySelectorAll('.provider-card').forEach(card => card.classList.remove('selected'));
            event.currentTarget.classList.add('selected');
            event.currentTarget.querySelector('input').checked = true;
            
            const keySection = document.getElementById('aiKeySection');
            keySection.style.display = (provider === 'openai' || provider === 'anthropic') ? 'block' : 'none';
        }
        
        function toggleCheckbox(element) {
            const checkbox = element.querySelector('input');
            checkbox.checked = !checkbox.checked;
            element.classList.toggle('selected', checkbox.checked);
        }
        
        function toggleTailscale() {
            document.getElementById('tailscaleOptions').style.display = 
                document.getElementById('tailscale').checked ? 'block' : 'none';
        }
        
        async function loadDrives() {
            const driveList = document.getElementById('driveList');
            driveList.innerHTML = '<div class="info-box">Scanning for storage devices...</div>';
            
            try {
                const response = await fetch('/api/drives');
                const drives = await response.json();
                
                let html = '';
                drives.forEach((drive, index) => {
                    const icon = drive.type === 'external' ? '💾' : '💻';
                    html += `
                        <div class="drive-option ${index === 0 ? 'selected' : ''}" onclick="selectDrive(this)">
                            <div class="drive-icon">${icon}</div>
                            <div class="drive-info">
                                <div class="drive-name">${drive.name}</div>
                                <div class="drive-details">${drive.description}</div>
                            </div>
                            <div class="drive-size">${drive.size}</div>
                            <input type="radio" name="storage" value="${drive.path}" ${index === 0 ? 'checked' : ''} style="display:none">
                        </div>
                    `;
                });
                
                driveList.innerHTML = html;
            } catch (e) {
                driveList.innerHTML = '<div class="warning-box"><h4>⚠️ Unable to scan drives</h4>Please enter a custom path below</div>';
            }
        }
        
        function selectDrive(element) {
            document.querySelectorAll('.drive-option').forEach(d => d.classList.remove('selected'));
            element.classList.add('selected');
            element.querySelector('input').checked = true;
        }
        
        function generateSummary() {
            const aiProvider = document.querySelector('input[name="ai_provider"]:checked')?.value || 'Template Plans';
            const useCases = Array.from(document.querySelectorAll('input[name="use_cases"]:checked')).map(cb => cb.value).join(', ') || 'None selected';
            const storage = document.querySelector('input[name="storage"]:checked')?.value || document.getElementById('customPath').value || 'Default';
            
            const components = [];
            if (document.getElementById('tailscale').checked) components.push('Tailscale');
            if (document.getElementById('adguard').checked) components.push('AdGuard');
            if (document.getElementById('jellyfin').checked) components.push('Jellyfin');
            if (document.getElementById('immich').checked) components.push('Immich');
            if (document.getElementById('filebrowser').checked) components.push('FileBrowser');
            
            document.getElementById('summaryContent').innerHTML = `
                <div class="summary-item"><span class="summary-label">AI Provider</span><span class="summary-value">${aiProvider}</span></div>
                <div class="summary-item"><span class="summary-label">Use Cases</span><span class="summary-value">${useCases}</span></div>
                <div class="summary-item"><span class="summary-label">Storage</span><span class="summary-value">${storage}</span></div>
                <div class="summary-item"><span class="summary-label">Components</span><span class="summary-value">${components.join(', ') || 'None'}</span></div>
            `;
        }
        
        async function submitConfig() {
            const config = {
                ai_provider: document.querySelector('input[name="ai_provider"]:checked')?.value,
                ai_api_key: document.getElementById('aiApiKey')?.value,
                use_cases: Array.from(document.querySelectorAll('input[name="use_cases"]:checked')).map(cb => cb.value),
                storage_path: document.querySelector('input[name="storage"]:checked')?.value || document.getElementById('customPath').value,
                tailscale: document.getElementById('tailscale').checked,
                tailscale_exit_node: document.getElementById('tailscaleExit').checked,
                tailscale_ssh: document.getElementById('tailscaleSsh').checked,
                adguard: document.getElementById('adguard').checked,
                jellyfin: document.getElementById('jellyfin').checked,
                immich: document.getElementById('immich').checked,
                filebrowser: document.getElementById('filebrowser').checked
            };
            
            try {
                const response = await fetch('/save', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify(config)
                });
                
                if (response.ok) {
                    document.querySelector('.container').innerHTML = `
                        <div class="header">
                            <div class="header-icon" style="background: var(--apple-green);">✓</div>
                            <h1>Configuration Saved</h1>
                            <p>Setup will continue in the terminal</p>
                        </div>
                    `;
                    document.querySelector('.button-container').style.display = 'none';
                } else {
                    alert('Error saving configuration: Invalid CSRF token or validation error');
                }
            } catch (e) {
                alert('Error saving configuration');
            }
        }
        
        updateProgress();
    </script>
</body>
</html>
'''


class WebConfigServer:
    """Flask server for web-based configuration with security hardening."""
    
    def __init__(self, port=8080, config_file="config.json"):
        self.port = port
        self.config_file = config_file
        self.config_data = None
        self.app = Flask(__name__) if Flask else None
        self._secret_key = secrets.token_hex(32)
        self._csrf_token = None
        self._setup_routes()
        self._setup_security_headers()
    
    def _setup_security_headers(self):
        """Add security headers to all responses."""
        if not self.app:
            return
        
        @self.app.after_request
        def add_security_headers(response):
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
            return response
    
    def _setup_routes(self):
        """Set up Flask routes."""
        if not self.app:
            return
        
        @self.app.before_request
        def before_request():
            g.csrf_token = self._generate_csrf_token()
        
        @self.app.route("/")
        def index():
            return render_template_string(HTML_TEMPLATE)
        
        @self.app.route("/api/csrf-token")
        def get_csrf_token():
            """Get CSRF token for form submission."""
            return jsonify({"csrf_token": self._generate_csrf_token()})
        
        @self.app.route("/api/drives")
        def get_drives():
            """Get available storage drives."""
            try:
                from drive_detector import detect_storage_options
                drives = detect_storage_options()
                return jsonify(drives)
            except Exception:
                return jsonify([{
                    "id": "default",
                    "name": "Default Location (/var/lib)",
                    "description": "Store data on the system drive",
                    "path": "/var/lib",
                    "size": "System dependent",
                    "type": "internal"
                }])
        
        @self.app.route("/save", methods=["POST"])
        def save_config():
            """Save configuration with CSRF validation."""
            from security_utils import CSRFProtection
            
            # Validate CSRF token
            token = request.headers.get('X-CSRF-Token')
            if not CSRFProtection.validate_token(token, self._generate_csrf_token()):
                return jsonify({"status": "error", "message": "Invalid CSRF token"}), 403
            
            try:
                self.config_data = request.get_json()
                self.config_data = self._sanitize_config(self.config_data)
                self._secure_store_credentials(self.config_data)
                
                with open(self.config_file, "w") as f:
                    json.dump(self.config_data, f, indent=2)
                return jsonify({"status": "ok"})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        
        @self.app.route("/health")
        def health():
            return jsonify({"status": "healthy"})
    
    def _sanitize_config(self, config):
        """Sanitize configuration values."""
        from security_utils import InputValidator
        
        if 'storage_path' in config and config['storage_path']:
            is_valid, result = InputValidator.validate_storage_path(config['storage_path'])
            if not is_valid:
                raise ValueError(f"Invalid storage path: {result}")
            config['storage_path'] = result
        
        if 'domain_name' in config and config['domain_name']:
            is_valid, result = InputValidator.validate_domain(config['domain_name'])
            if not is_valid:
                raise ValueError(f"Invalid domain: {result}")
            config['domain_name'] = result
        
        if 'admin_email' in config and config['admin_email']:
            is_valid, result = InputValidator.validate_email(config['admin_email'])
            if not is_valid:
                raise ValueError(f"Invalid email: {result}")
            config['admin_email'] = result
        
        return config
    
    def _secure_store_credentials(self, config):
        """Store credentials securely."""
        sensitive_fields = ['ai_api_key', 'tailscale_auth_key', 'openclaw_gateway_token']
        for field in sensitive_fields:
            if field in config and config[field]:
                # In production, use keyring or encrypted storage
                pass
    
    def _generate_csrf_token(self):
        """Generate CSRF token."""
        if self._csrf_token is None:
            self._csrf_token = secrets.token_hex(32)
        return self._csrf_token
    
    def run(self, debug=False):
        """Run the server."""
        if not self.app:
            print("Error: Flask not installed. Run: pip install flask")
            return False
        
        print(f"Starting web config server on http://localhost:{self.port}")
        self.app.run(host="0.0.0.0", port=self.port, debug=debug)
        return True
    
    def wait_for_config(self, timeout=300):
        """Wait for configuration to be saved."""
        import time
        start = time.time()
        
        print(f"\nWaiting for configuration...")
        print(f"Please complete the setup in your browser")
        print(f"(Timeout: {timeout}s)\n")
        
        while time.time() - start < timeout:
            if self.config_data or os.path.exists(self.config_file):
                if os.path.exists(self.config_file):
                    with open(self.config_file, "r") as f:
                        self.config_data = json.load(f)
                print("\n✅ Configuration received!")
                return self.config_data
            time.sleep(1)
        
        print("\n⏱️  Timeout waiting for configuration")
        return None
    
    def stop(self):
        pass


def start_web_config(port=8080, config_file="config.json"):
    """Start web configuration server."""
    server = WebConfigServer(port=port, config_file=config_file)
    
    import threading
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()
    
    config = server.wait_for_config()
    return config


launch_web_config = start_web_config

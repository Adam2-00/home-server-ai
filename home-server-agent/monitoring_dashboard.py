#!/usr/bin/env python3
"""
Monitoring Dashboard for Home Server Agent
Real-time service monitoring, system metrics, and service management.
"""
import os
import sys
import json
import sqlite3
import subprocess
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# Optional imports with fallbacks
try:
    import psutil
except ImportError:
    psutil = None

try:
    from flask import Flask, render_template_string, request, jsonify, Response
except ImportError:
    Flask = None
    render_template_string = None
    request = None
    jsonify = None
    Response = None

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class ServiceStatus:
    """Status of a single service."""
    name: str
    installed: bool
    running: bool
    healthy: bool
    version: Optional[str]
    ports: List[int]
    uptime_seconds: Optional[int]
    last_check: str
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float
    cpu_count: int
    ram_total_gb: float
    ram_used_gb: float
    ram_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_percent: float
    load_average: Tuple[float, float, float]
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            'cpu_percent': self.cpu_percent,
            'cpu_count': self.cpu_count,
            'ram_total_gb': round(self.ram_total_gb, 2),
            'ram_used_gb': round(self.ram_used_gb, 2),
            'ram_percent': round(self.ram_percent, 1),
            'disk_total_gb': round(self.disk_total_gb, 2),
            'disk_used_gb': round(self.disk_used_gb, 2),
            'disk_percent': round(self.disk_percent, 1),
            'load_average': list(self.load_average),
            'timestamp': self.timestamp
        }


class ServiceMonitor:
    """Monitors the status of installed services."""
    
    SERVICES = {
        'tailscale': {
            'check_cmd': ['tailscale', 'version'],
            'status_cmd': ['tailscale', 'status'],
            'ports': [41641],
            'systemd_service': 'tailscaled',
            'health_url': None,
        },
        'adguard': {
            'check_cmd': ['docker', 'ps'],
            'container_name': 'adguardhome',
            'ports': [53, 3000],
            'systemd_service': None,
            'health_url': 'http://localhost:3000',
        },
        'jellyfin': {
            'check_cmd': ['docker', 'ps'],
            'container_name': 'jellyfin',
            'ports': [8096],
            'systemd_service': None,
            'health_url': 'http://localhost:8096',
        },
        'immich': {
            'check_cmd': ['docker', 'ps'],
            'container_name': 'immich_server',
            'ports': [2283],
            'systemd_service': None,
            'health_url': 'http://localhost:2283',
        },
        'openclaw': {
            'check_cmd': ['which', 'openclaw'],
            'ports': [],
            'systemd_service': 'openclaw',
            'health_url': None,
        },
        'docker': {
            'check_cmd': ['docker', 'version'],
            'ports': [],
            'systemd_service': 'docker',
            'health_url': None,
        }
    }
    
    def __init__(self):
        self.status_cache: Dict[str, ServiceStatus] = {}
        self.last_update: Optional[str] = None
    
    def get_all_statuses(self) -> Dict[str, ServiceStatus]:
        """Get status of all services."""
        statuses = {}
        for service_name, config in self.SERVICES.items():
            statuses[service_name] = self._check_service(service_name, config)
        self.status_cache = statuses
        self.last_update = datetime.now().isoformat()
        return statuses
    
    def _check_service(self, name: str, config: Dict) -> ServiceStatus:
        """Check status of a single service."""
        now = datetime.now().isoformat()
        
        # Check if installed
        installed = self._is_installed(config.get('check_cmd', []), config.get('container_name'))
        
        if not installed:
            return ServiceStatus(
                name=name,
                installed=False,
                running=False,
                healthy=False,
                version=None,
                ports=config.get('ports', []),
                uptime_seconds=None,
                last_check=now
            )
        
        # Check if running
        running = self._is_running(name, config)
        
        # Get version
        version = self._get_version(name, config) if installed else None
        
        # Health check
        healthy = False
        error_msg = None
        if running:
            healthy, error_msg = self._health_check(config)
        
        # Get uptime
        uptime = self._get_uptime(config) if running else None
        
        return ServiceStatus(
            name=name,
            installed=installed,
            running=running,
            healthy=healthy and running,
            version=version,
            ports=config.get('ports', []),
            uptime_seconds=uptime,
            last_check=now,
            error_message=error_msg
        )
    
    def _is_installed(self, check_cmd: List[str], container_name: Optional[str] = None) -> bool:
        """Check if service is installed."""
        if not check_cmd:
            return False
        
        try:
            if container_name and 'docker' in check_cmd:
                # Check for container
                result = subprocess.run(
                    ['docker', 'ps', '-a', '--filter', f'name={container_name}', '--format', '{{.Names}}'],
                    capture_output=True, text=True, timeout=10
                )
                return container_name in result.stdout
            else:
                result = subprocess.run(check_cmd, capture_output=True, timeout=5)
                return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _is_running(self, name: str, config: Dict) -> bool:
        """Check if service is running."""
        container_name = config.get('container_name')
        systemd_service = config.get('systemd_service')
        
        # Check container
        if container_name:
            try:
                result = subprocess.run(
                    ['docker', 'ps', '--filter', f'name={container_name}', '--filter', 'status=running', '--format', '{{.Names}}'],
                    capture_output=True, text=True, timeout=10
                )
                return container_name in result.stdout
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return False
        
        # Check systemd service
        if systemd_service:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', systemd_service],
                    capture_output=True, timeout=5
                )
                return result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return False
        
        # Default: assume running if installed
        return True
    
    def _get_version(self, name: str, config: Dict) -> Optional[str]:
        """Get service version."""
        version_cmds = {
            'tailscale': ['tailscale', 'version'],
            'docker': ['docker', 'version', '--format', '{{.Server.Version}}'],
            'openclaw': ['openclaw', '--version'],
        }
        
        if name in version_cmds:
            try:
                result = subprocess.run(version_cmds[name], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return result.stdout.strip().split('\n')[0][:50]
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        # For Docker containers, get image version
        if config.get('container_name'):
            try:
                result = subprocess.run(
                    ['docker', 'inspect', '--format={{.Config.Image}}', config['container_name']],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        return None
    
    def _health_check(self, config: Dict) -> Tuple[bool, Optional[str]]:
        """Perform health check on service."""
        health_url = config.get('health_url')
        
        if health_url:
            try:
                import urllib.request
                req = urllib.request.Request(health_url, method='HEAD')
                req.add_header('User-Agent', 'HomeServerMonitor/1.0')
                with urllib.request.urlopen(req, timeout=5) as response:
                    return True, None
            except Exception as e:
                return False, str(e)
        
        return True, None
    
    def _get_uptime(self, config: Dict) -> Optional[int]:
        """Get service uptime in seconds."""
        container_name = config.get('container_name')
        systemd_service = config.get('systemd_service')
        
        if container_name:
            try:
                result = subprocess.run(
                    ['docker', 'inspect', '--format={{.State.StartedAt}}', container_name],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    started_at = result.stdout.strip()
                    # Parse Docker timestamp
                    started_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    uptime = (datetime.now().replace(tzinfo=started_dt.tzinfo) - started_dt).total_seconds()
                    return int(uptime)
            except Exception:
                pass
        
        if systemd_service:
            try:
                result = subprocess.run(
                    ['systemctl', 'show', systemd_service, '--property=ActiveEnterTimestamp'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and 'ActiveEnterTimestamp=' in result.stdout:
                    timestamp_str = result.stdout.strip().split('=', 1)[1]
                    if timestamp_str and timestamp_str != 'n/a':
                        # Parse systemd timestamp
                        started_dt = datetime.fromisoformat(timestamp_str.replace(' ', 'T'))
                        uptime = (datetime.now() - started_dt).total_seconds()
                        return int(uptime)
            except Exception:
                pass
        
        return None
    
    def control_service(self, name: str, action: str) -> Tuple[bool, str]:
        """Control a service (start, stop, restart)."""
        if name not in self.SERVICES:
            return False, f"Unknown service: {name}"
        
        config = self.SERVICES[name]
        container_name = config.get('container_name')
        systemd_service = config.get('systemd_service')
        
        try:
            if container_name:
                if action == 'start':
                    cmd = ['docker', 'start', container_name]
                elif action == 'stop':
                    cmd = ['docker', 'stop', container_name]
                elif action == 'restart':
                    cmd = ['docker', 'restart', container_name]
                else:
                    return False, f"Invalid action: {action}"
            elif systemd_service:
                if action in ['start', 'stop', 'restart']:
                    cmd = ['sudo', 'systemctl', action, systemd_service]
                else:
                    return False, f"Invalid action: {action}"
            else:
                return False, f"Cannot control {name}: no container or service defined"
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return True, f"{name} {action}ed successfully"
            else:
                return False, f"Failed to {action} {name}: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, f"Timeout while trying to {action} {name}"
        except FileNotFoundError:
            return False, f"Command not found for {action}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def get_logs(self, name: str, lines: int = 100) -> str:
        """Get logs for a service."""
        if name not in self.SERVICES:
            return f"Unknown service: {name}"
        
        config = self.SERVICES[name]
        container_name = config.get('container_name')
        systemd_service = config.get('systemd_service')
        
        try:
            if container_name:
                result = subprocess.run(
                    ['docker', 'logs', '--tail', str(lines), container_name],
                    capture_output=True, text=True, timeout=10
                )
                return result.stdout if result.returncode == 0 else result.stderr
            elif systemd_service:
                result = subprocess.run(
                    ['journalctl', '-u', systemd_service, '-n', str(lines), '--no-pager'],
                    capture_output=True, text=True, timeout=10
                )
                return result.stdout if result.returncode == 0 else result.stderr
            else:
                return f"No logs available for {name}"
        except Exception as e:
            return f"Error getting logs: {str(e)}"


class SystemMonitor:
    """Monitors system resources."""
    
    def get_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        if psutil:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory
            mem = psutil.virtual_memory()
            ram_total_gb = mem.total / (1024**3)
            ram_used_gb = mem.used / (1024**3)
            ram_percent = mem.percent
            
            # Disk (root partition)
            disk = psutil.disk_usage('/')
            disk_total_gb = disk.total / (1024**3)
            disk_used_gb = disk.used / (1024**3)
            disk_percent = disk.percent
            
            # Load average
            try:
                load_avg = os.getloadavg()
            except OSError:
                load_avg = (0.0, 0.0, 0.0)
        else:
            # Fallback values
            cpu_percent = 0.0
            cpu_count = 1
            ram_total_gb = 0.0
            ram_used_gb = 0.0
            ram_percent = 0.0
            disk_total_gb = 0.0
            disk_used_gb = 0.0
            disk_percent = 0.0
            load_avg = (0.0, 0.0, 0.0)
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            ram_total_gb=ram_total_gb,
            ram_used_gb=ram_used_gb,
            ram_percent=ram_percent,
            disk_total_gb=disk_total_gb,
            disk_used_gb=disk_used_gb,
            disk_percent=disk_percent,
            load_average=load_avg,
            timestamp=datetime.now().isoformat()
        )


# HTML Template for the monitoring dashboard
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Home Server Monitor</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        :root {
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --bg-hover: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --accent: #3b82f6;
            --success: #22c55e;
            --warning: #f59e0b;
            --error: #ef4444;
            --info: #06b6d4;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
            text-align: center;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        }
        
        .header h1 {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        
        .header p {
            opacity: 0.9;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .metric-card {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.5rem;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        }
        
        .metric-label {
            color: var(--text-secondary);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
        
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        
        .metric-bar {
            height: 8px;
            background: var(--bg-hover);
            border-radius: 4px;
            overflow: hidden;
        }
        
        .metric-bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }
        
        .metric-bar-fill.low { background: var(--success); }
        .metric-bar-fill.medium { background: var(--warning); }
        .metric-bar-fill.high { background: var(--error); }
        
        .services-section {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .section-title {
            font-size: 1.25rem;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .service-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1rem;
        }
        
        .service-card {
            background: var(--bg-dark);
            border-radius: 8px;
            padding: 1rem;
            border-left: 4px solid var(--text-secondary);
            transition: all 0.2s;
        }
        
        .service-card.installed { border-left-color: var(--success); }
        .service-card.running { border-left-color: var(--accent); }
        .service-card.error { border-left-color: var(--error); }
        .service-card:not(.installed) { opacity: 0.6; }
        
        .service-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        
        .service-name {
            font-weight: 600;
            font-size: 1.1rem;
        }
        
        .service-status {
            display: flex;
            align-items: center;
            gap: 0.25rem;
            font-size: 0.875rem;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            background: var(--bg-hover);
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        
        .status-dot.running { background: var(--success); box-shadow: 0 0 8px var(--success); }
        .status-dot.stopped { background: var(--error); }
        .status-dot.not-installed { background: var(--text-secondary); }
        
        .service-info {
            color: var(--text-secondary);
            font-size: 0.875rem;
            margin-bottom: 0.5rem;
        }
        
        .service-controls {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.75rem;
        }
        
        .btn {
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.875rem;
            font-weight: 500;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .btn-primary {
            background: var(--accent);
            color: white;
        }
        
        .btn-primary:hover:not(:disabled) {
            background: #2563eb;
        }
        
        .btn-success {
            background: var(--success);
            color: white;
        }
        
        .btn-success:hover:not(:disabled) {
            background: #16a34a;
        }
        
        .btn-danger {
            background: var(--error);
            color: white;
        }
        
        .btn-danger:hover:not(:disabled) {
            background: #dc2626;
        }
        
        .btn-secondary {
            background: var(--bg-hover);
            color: var(--text-primary);
        }
        
        .btn-secondary:hover:not(:disabled) {
            background: #475569;
        }
        
        .logs-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            padding: 2rem;
        }
        
        .logs-modal.active {
            display: flex;
        }
        
        .logs-content {
            background: var(--bg-card);
            border-radius: 12px;
            width: 100%;
            max-width: 900px;
            max-height: 80vh;
            display: flex;
            flex-direction: column;
        }
        
        .logs-header {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--bg-hover);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logs-body {
            padding: 1rem;
            overflow-y: auto;
            font-family: 'Fira Code', 'Consolas', monospace;
            font-size: 0.875rem;
            white-space: pre-wrap;
            word-break: break-all;
            max-height: 60vh;
        }
        
        .refresh-indicator {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: var(--accent);
            color: white;
            padding: 0.75rem 1rem;
            border-radius: 8px;
            display: none;
            align-items: center;
            gap: 0.5rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .refresh-indicator.active {
            display: flex;
        }
        
        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .toast {
            position: fixed;
            bottom: 2rem;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: var(--bg-card);
            color: var(--text-primary);
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            transition: transform 0.3s ease;
            z-index: 1001;
        }
        
        .toast.show {
            transform: translateX(-50%) translateY(0);
        }
        
        .toast.success { border-left: 4px solid var(--success); }
        .toast.error { border-left: 4px solid var(--error); }
        
        @media (max-width: 768px) {
            .container {
                padding: 1rem;
            }
            
            .metrics-grid {
                grid-template-columns: 1fr;
            }
            
            .service-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏠 Home Server Monitor</h1>
        <p>Real-time service monitoring and system metrics</p>
    </div>
    
    <div class="container">
        <!-- System Metrics -->
        <div class="metrics-grid" id="metrics">
            <!-- Populated by JS -->
        </div>
        
        <!-- Services -->
        <div class="services-section">
            <h2 class="section-title">🚀 Services</h2>
            <div class="service-grid" id="services">
                <!-- Populated by JS -->
            </div>
        </div>
    </div>
    
    <!-- Logs Modal -->
    <div class="logs-modal" id="logsModal">
        <div class="logs-content">
            <div class="logs-header">
                <h3 id="logsTitle">Service Logs</h3>
                <button class="btn btn-secondary" onclick="closeLogs()">Close</button>
            </div>
            <div class="logs-body" id="logsBody">Loading...</div>
        </div>
    </div>
    
    <!-- Refresh Indicator -->
    <div class="refresh-indicator" id="refreshIndicator">
        <div class="spinner"></div>
        <span>Refreshing...</span>
    </div>
    
    <!-- Toast -->
    <div class="toast" id="toast"></div>
    
    <script>
        let autoRefreshInterval;
        
        // Fetch and display metrics
        async function loadMetrics() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();
                renderMetrics(data);
            } catch (error) {
                console.error('Failed to load metrics:', error);
            }
        }
        
        // Fetch and display services
        async function loadServices() {
            try {
                const response = await fetch('/api/services');
                const data = await response.json();
                renderServices(data);
            } catch (error) {
                console.error('Failed to load services:', error);
            }
        }
        
        // Render metrics cards
        function renderMetrics(metrics) {
            const container = document.getElementById('metrics');
            
            const metrics_data = [
                { label: 'CPU Usage', value: `${metrics.cpu_percent.toFixed(1)}%`, percent: metrics.cpu_percent },
                { label: 'Memory Usage', value: `${metrics.ram_percent.toFixed(1)}%`, subtext: `${metrics.ram_used_gb.toFixed(1)} / ${metrics.ram_total_gb.toFixed(1)} GB`, percent: metrics.ram_percent },
                { label: 'Disk Usage', value: `${metrics.disk_percent.toFixed(1)}%`, subtext: `${metrics.disk_used_gb.toFixed(1)} / ${metrics.disk_total_gb.toFixed(1)} GB`, percent: metrics.disk_percent },
                { label: 'Load Average', value: metrics.load_average[0].toFixed(2), subtext: '1 min average', percent: Math.min(metrics.load_average[0] * 100 / metrics.cpu_count, 100) }
            ];
            
            container.innerHTML = metrics_data.map(m => `
                <div class="metric-card">
                    <div class="metric-label">${m.label}</div>
                    <div class="metric-value">${m.value}</div>
                    ${m.subtext ? `<div class="metric-info" style="color: var(--text-secondary); font-size: 0.875rem; margin-bottom: 0.5rem;">${m.subtext}</div>` : ''}
                    <div class="metric-bar">
                        <div class="metric-bar-fill ${m.percent < 50 ? 'low' : m.percent < 80 ? 'medium' : 'high'}" style="width: ${Math.min(m.percent, 100)}%"></div>
                    </div>
                </div>
            `).join('');
        }
        
        // Render service cards
        function renderServices(services) {
            const container = document.getElementById('services');
            
            container.innerHTML = Object.entries(services).map(([name, service]) => {
                const statusClass = service.running ? 'running' : service.installed ? 'installed' : '';
                const statusText = service.running ? 'Running' : service.installed ? 'Installed' : 'Not Installed';
                const statusDotClass = service.running ? 'running' : service.installed ? 'stopped' : 'not-installed';
                
                return `
                    <div class="service-card ${statusClass}">
                        <div class="service-header">
                            <span class="service-name">${name.charAt(0).toUpperCase() + name.slice(1)}</span>
                            <span class="service-status">
                                <span class="status-dot ${statusDotClass}"></span>
                                ${statusText}
                            </span>
                        </div>
                        <div class="service-info">
                            ${service.version ? `Version: ${service.version}<br>` : ''}
                            ${service.ports.length ? `Ports: ${service.ports.join(', ')}<br>` : ''}
                            ${service.uptime_seconds ? `Uptime: ${formatUptime(service.uptime_seconds)}<br>` : ''}
                            ${service.error_message ? `<span style="color: var(--error);">Error: ${service.error_message}</span>` : ''}
                        </div>
                        <div class="service-controls">
                            ${service.installed ? `
                                ${service.running ? `
                                    <button class="btn btn-danger" onclick="controlService('${name}', 'stop')">⏹ Stop</button>
                                    <button class="btn btn-primary" onclick="controlService('${name}', 'restart')">🔄 Restart</button>
                                ` : `
                                    <button class="btn btn-success" onclick="controlService('${name}', 'start')">▶ Start</button>
                                `}
                                <button class="btn btn-secondary" onclick="viewLogs('${name}')">📄 Logs</button>
                            ` : '<span style="color: var(--text-secondary); font-size: 0.875rem;">Not installed</span>'}
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        // Format uptime
        function formatUptime(seconds) {
            const days = Math.floor(seconds / 86400);
            const hours = Math.floor((seconds % 86400) / 3600);
            const mins = Math.floor((seconds % 3600) / 60);
            
            if (days > 0) return `${days}d ${hours}h ${mins}m`;
            if (hours > 0) return `${hours}h ${mins}m`;
            return `${mins}m`;
        }
        
        // Control service (start/stop/restart)
        async function controlService(name, action) {
            showRefreshIndicator();
            try {
                const response = await fetch(`/api/services/${name}/${action}`, { method: 'POST' });
                const result = await response.json();
                
                if (result.success) {
                    showToast(result.message, 'success');
                    setTimeout(() => loadServices(), 1000);
                } else {
                    showToast(result.error, 'error');
                }
            } catch (error) {
                showToast(`Failed to ${action} ${name}`, 'error');
            } finally {
                hideRefreshIndicator();
            }
        }
        
        // View logs
        async function viewLogs(name) {
            document.getElementById('logsTitle').textContent = `${name} Logs`;
            document.getElementById('logsBody').textContent = 'Loading...';
            document.getElementById('logsModal').classList.add('active');
            
            try {
                const response = await fetch(`/api/services/${name}/logs`);
                const logs = await response.text();
                document.getElementById('logsBody').textContent = logs || 'No logs available';
            } catch (error) {
                document.getElementById('logsBody').textContent = 'Failed to load logs';
            }
        }
        
        // Close logs modal
        function closeLogs() {
            document.getElementById('logsModal').classList.remove('active');
        }
        
        // Show/hide refresh indicator
        function showRefreshIndicator() {
            document.getElementById('refreshIndicator').classList.add('active');
        }
        
        function hideRefreshIndicator() {
            document.getElementById('refreshIndicator').classList.remove('active');
        }
        
        // Show toast notification
        function showToast(message, type) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = `toast ${type} show`;
            
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }
        
        // Refresh all data
        async function refreshAll() {
            showRefreshIndicator();
            await Promise.all([loadMetrics(), loadServices()]);
            hideRefreshIndicator();
        }
        
        // Auto-refresh toggle
        function toggleAutoRefresh(enabled) {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }
            
            if (enabled) {
                autoRefreshInterval = setInterval(refreshAll, 5000); // Refresh every 5 seconds
            }
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            refreshAll();
            toggleAutoRefresh(true);
        });
        
        // Close modal on click outside
        document.getElementById('logsModal').addEventListener('click', (e) => {
            if (e.target.id === 'logsModal') {
                closeLogs();
            }
        });
    </script>
</body>
</html>
'''


class MonitoringDashboard:
    """Web-based monitoring dashboard."""
    
    def __init__(self, port: int = 8081, db_path: str = "state.db"):
        if Flask is None:
            raise ImportError(
                "Flask not installed. Run: pip3 install flask\n"
                "Required for monitoring dashboard."
            )
        
        self.port = port
        self.db_path = db_path
        self.app = Flask(__name__)
        self.service_monitor = ServiceMonitor()
        self.system_monitor = SystemMonitor()
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up Flask routes."""
        
        @self.app.route('/')
        def index():
            return render_template_string(DASHBOARD_HTML)
        
        @self.app.route('/api/metrics')
        def api_metrics():
            """Get system metrics."""
            metrics = self.system_monitor.get_metrics()
            return jsonify(metrics.to_dict())
        
        @self.app.route('/api/services')
        def api_services():
            """Get service statuses."""
            statuses = self.service_monitor.get_all_statuses()
            return jsonify({
                name: status.to_dict()
                for name, status in statuses.items()
            })
        
        @self.app.route('/api/services/<name>/<action>', methods=['POST'])
        def api_control_service(name: str, action: str):
            """Control a service (start/stop/restart)."""
            if action not in ['start', 'stop', 'restart']:
                return jsonify({'success': False, 'error': 'Invalid action'}), 400
            
            success, message = self.service_monitor.control_service(name, action)
            return jsonify({
                'success': success,
                'message' if success else 'error': message
            })
        
        @self.app.route('/api/services/<name>/logs')
        def api_service_logs(name: str):
            """Get service logs."""
            logs = self.service_monitor.get_logs(name)
            return Response(logs, mimetype='text/plain')
        
        @self.app.route('/api/session')
        def api_session():
            """Get current session info."""
            session_info = self._get_session_info()
            return jsonify(session_info)
        
        @self.app.route('/health')
        def health():
            """Health check endpoint."""
            return jsonify({'status': 'ok'})
    
    def _get_session_info(self) -> Dict:
        """Get information about the current setup session."""
        path = Path(self.db_path)
        if not path.exists():
            return {'status': 'no_database'}
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT session_id, status, current_step, created_at, updated_at 
                FROM sessions 
                ORDER BY updated_at DESC 
                LIMIT 1
            ''')
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'status': 'found',
                    'session_id': row[0],
                    'setup_status': row[1],
                    'current_step': row[2],
                    'created_at': row[3],
                    'updated_at': row[4]
                }
            return {'status': 'no_sessions'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def run(self, debug: bool = False):
        """Run the dashboard server."""
        print(f"🌐 Starting monitoring dashboard on http://localhost:{self.port}")
        print(f"   Press Ctrl+C to stop")
        self.app.run(host='0.0.0.0', port=self.port, debug=debug)


def start_dashboard(port: int = 8081, db_path: str = "state.db"):
    """Convenience function to start the dashboard."""
    dashboard = MonitoringDashboard(port=port, db_path=db_path)
    dashboard.run()


def check_services() -> Dict[str, ServiceStatus]:
    """Quick check of all services (CLI use)."""
    monitor = ServiceMonitor()
    return monitor.get_all_statuses()


def print_status():
    """Print service status to console."""
    monitor = ServiceMonitor()
    system = SystemMonitor()
    
    print("\n" + "="*60)
    print("  🏠 Home Server Status")
    print("="*60)
    
    # System metrics
    metrics = system.get_metrics()
    print(f"\n📊 System Metrics:")
    print(f"   CPU: {metrics.cpu_percent:.1f}% ({metrics.cpu_count} cores)")
    print(f"   RAM: {metrics.ram_percent:.1f}% ({metrics.ram_used_gb:.1f}/{metrics.ram_total_gb:.1f} GB)")
    print(f"   Disk: {metrics.disk_percent:.1f}% ({metrics.disk_used_gb:.1f}/{metrics.disk_total_gb:.1f} GB)")
    print(f"   Load: {metrics.load_average[0]:.2f}, {metrics.load_average[1]:.2f}, {metrics.load_average[2]:.2f}")
    
    # Services
    print(f"\n🚀 Services:")
    statuses = monitor.get_all_statuses()
    for name, status in statuses.items():
        if status.installed:
            icon = "✅" if status.running else "⏹️"
            health = " (healthy)" if status.healthy else ""
            version = f" v{status.version}" if status.version else ""
            print(f"   {icon} {name}{version}: {status.running and 'Running' or 'Stopped'}{health}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Home Server Monitoring Dashboard')
    parser.add_argument('--port', type=int, default=8081, help='Dashboard port (default: 8081)')
    parser.add_argument('--cli', action='store_true', help='Show status in CLI instead of web')
    parser.add_argument('--db', type=str, default='state.db', help='Path to state database')
    
    args = parser.parse_args()
    
    if args.cli:
        print_status()
    else:
        start_dashboard(port=args.port, db_path=args.db)

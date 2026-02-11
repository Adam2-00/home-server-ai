"""
Pre-flight Validation Module
Checks system readiness before installation begins.
"""
import os
import shutil
import subprocess
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import socket
import re
import time



@dataclass
class ValidationResult:
    """Result of a validation check."""
    name: str
    passed: bool
    message: str
    severity: str  # 'info', 'warning', 'error', 'critical'
    suggested_fix: str = ""


class PreflightValidator:
    """Validates system readiness before installation."""
    
    # Minimum requirements
    MIN_RAM_GB = 1
    MIN_DISK_GB = 5
    MIN_CPU_CORES = 1
    
    def __init__(self):
        self.results: List[ValidationResult] = []
    
    def run_all_checks(self, storage_path: str = None, domain_config: Dict = None) -> List[ValidationResult]:
        """Run all pre-flight checks."""
        self.results = []
        
        self.check_python_version()
        self.check_disk_space(storage_path)
        self.check_write_permissions(storage_path)
        self.check_internet_connectivity()
        self.check_port_availability()
        self.check_system_resources()
        self.check_sudo_access()
        self.check_docker_availability()
        self.check_systemd_status()
        self.check_dns_configuration()
        
        # Extended checks for common issues
        self.check_docker_daemon_socket()
        self.check_docker_storage_driver()
        self.check_docker_network_conflicts()
        self.check_ssl_certificate_capability()
        self.check_firewall_configuration()
        self.check_port_forwarding_requirement(domain_config)
        self.check_backup_destination(storage_path)
        self.check_update_policy()
        self.check_timezone_configuration()
        self.check_log_rotation()
        self.check_memory_swap()
        self.check_kernel_version()
        self.check_apparmor_selinux()
        self.check_disk_io_performance()
        
        return self.results
    
    def has_blocking_issues(self) -> bool:
        """Check if there are any critical errors that block installation."""
        return any(r.severity == 'critical' and not r.passed for r in self.results)
    
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(r.severity == 'warning' and not r.passed for r in self.results)
    
    def get_summary(self) -> Tuple[int, int, int]:
        """Return (passed, warnings, errors) counts."""
        passed = sum(1 for r in self.results if r.passed)
        warnings = sum(1 for r in self.results if not r.passed and r.severity == 'warning')
        errors = sum(1 for r in self.results if not r.passed and r.severity in ('error', 'critical'))
        return passed, warnings, errors
    
    def check_python_version(self):
        """Check Python version compatibility."""
        import sys
        version = sys.version_info
        
        if version < (3, 11):
            self.results.append(ValidationResult(
                name="Python Version",
                passed=False,
                message=f"Python 3.11+ required, found {version.major}.{version.minor}",
                severity='critical',
                suggested_fix="Upgrade Python to 3.11 or later"
            ))
        else:
            self.results.append(ValidationResult(
                name="Python Version",
                passed=True,
                message=f"Python {version.major}.{version.minor}.{version.micro} ✓",
                severity='info'
            ))
    
    def check_disk_space(self, storage_path: str = None):
        """Check available disk space."""
        # Check root partition
        try:
            root_stat = shutil.disk_usage("/")
            root_free_gb = root_stat.free / (1024**3)
            
            if root_free_gb < self.MIN_DISK_GB:
                self.results.append(ValidationResult(
                    name="Root Disk Space",
                    passed=False,
                    message=f"Only {root_free_gb:.1f}GB free on root (need {self.MIN_DISK_GB}GB+)",
                    severity='critical',
                    suggested_fix=f"Free up at least {self.MIN_DISK_GB - root_free_gb:.1f}GB of disk space"
                ))
            elif root_free_gb < self.MIN_DISK_GB * 2:
                self.results.append(ValidationResult(
                    name="Root Disk Space",
                    passed=True,
                    message=f"{root_free_gb:.1f}GB free on root (low but sufficient)",
                    severity='warning'
                ))
            else:
                self.results.append(ValidationResult(
                    name="Root Disk Space",
                    passed=True,
                    message=f"{root_free_gb:.1f}GB free on root ✓",
                    severity='info'
                ))
        except OSError as e:
            self.results.append(ValidationResult(
                name="Root Disk Space",
                passed=False,
                message=f"Cannot check disk space: {e}",
                severity='error',
                suggested_fix="Check permissions and try again"
            ))
        
        # Check storage path if specified
        if storage_path:
            path = Path(storage_path).expanduser()
            try:
                # Create path if it doesn't exist
                path.mkdir(parents=True, exist_ok=True)
                stat = shutil.disk_usage(path)
                free_gb = stat.free / (1024**3)
                
                if free_gb < self.MIN_DISK_GB:
                    self.results.append(ValidationResult(
                        name="Storage Path Space",
                        passed=False,
                        message=f"Only {free_gb:.1f}GB free at {path}",
                        severity='warning',
                        suggested_fix="Choose a different storage location with more space"
                    ))
                else:
                    self.results.append(ValidationResult(
                        name="Storage Path Space",
                        passed=True,
                        message=f"{free_gb:.1f}GB free at {path} ✓",
                        severity='info'
                    ))
            except (OSError, PermissionError) as e:
                self.results.append(ValidationResult(
                    name="Storage Path Space",
                    passed=False,
                    message=f"Cannot access {path}: {e}",
                    severity='error',
                    suggested_fix="Check permissions or choose a different path"
                ))
    
    def check_write_permissions(self, storage_path: str = None):
        """Check write permissions in working directory and storage path."""
        paths_to_check = [Path.cwd()]
        
        if storage_path:
            paths_to_check.append(Path(storage_path).expanduser())
        
        for path in paths_to_check:
            try:
                # Try to create a test file
                test_file = path / ".write_test"
                test_file.touch()
                test_file.unlink()
                self.results.append(ValidationResult(
                    name=f"Write Permission ({path.name if path.name else 'root'})",
                    passed=True,
                    message=f"Can write to {path} ✓",
                    severity='info'
                ))
            except (OSError, PermissionError) as e:
                self.results.append(ValidationResult(
                    name=f"Write Permission ({path.name if path.name else 'root'})",
                    passed=False,
                    message=f"Cannot write to {path}: {e}",
                    severity='critical' if path == Path.cwd() else 'error',
                    suggested_fix=f"Change permissions: chmod u+w {path}"
                ))
    
    def check_internet_connectivity(self):
        """Check internet connectivity with timeout."""
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '5', '8.8.8.8'],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                self.results.append(ValidationResult(
                    name="Internet Connectivity",
                    passed=True,
                    message="Internet connection OK ✓",
                    severity='info'
                ))
            else:
                self.results.append(ValidationResult(
                    name="Internet Connectivity",
                    passed=False,
                    message="Internet check failed (no response from 8.8.8.8)",
                    severity='warning',
                    suggested_fix="Check network connection - installation may fail"
                ))
        except subprocess.TimeoutExpired:
            self.results.append(ValidationResult(
                name="Internet Connectivity",
                passed=False,
                message="Internet check timed out (10s)",
                severity='warning',
                suggested_fix="Check network connection - installation may fail"
            ))
        except FileNotFoundError:
            self.results.append(ValidationResult(
                name="Internet Connectivity",
                passed=False,
                message="ping command not found",
                severity='warning',
                suggested_fix="Install iputils-ping package"
            ))
    
    def check_port_availability(self):
        """Check if common ports are already in use."""
        import socket
        
        common_ports = {
            53: "DNS (AdGuard)",
            80: "HTTP",
            443: "HTTPS",
            3000: "AdGuard Web UI",
            8080: "Alternative HTTP",
            8096: "Jellyfin",
        }
        
        conflicts = []
        for port, service in common_ports.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                
                if result == 0:
                    conflicts.append(f"{service} (port {port})")
            except socket.error:
                pass
        
        if conflicts:
            self.results.append(ValidationResult(
                name="Port Availability",
                passed=False,
                message=f"Some ports already in use: {', '.join(conflicts[:3])}",
                severity='warning',
                suggested_fix="Stop conflicting services or use different ports"
            ))
        else:
            self.results.append(ValidationResult(
                name="Port Availability",
                passed=True,
                message="Common ports available ✓",
                severity='info'
            ))
    
    def check_system_resources(self):
        """Check RAM and CPU."""
        try:
            import psutil
            
            # Check RAM
            mem = psutil.virtual_memory()
            ram_gb = mem.total / (1024**3)
            
            if ram_gb < self.MIN_RAM_GB:
                self.results.append(ValidationResult(
                    name="System RAM",
                    passed=False,
                    message=f"Only {ram_gb:.1f}GB RAM (need {self.MIN_RAM_GB}GB+)",
                    severity='error',
                    suggested_fix="Install more RAM or use a lighter setup"
                ))
            elif ram_gb < self.MIN_RAM_GB * 2:
                self.results.append(ValidationResult(
                    name="System RAM",
                    passed=True,
                    message=f"{ram_gb:.1f}GB RAM (minimum met)",
                    severity='warning'
                ))
            else:
                self.results.append(ValidationResult(
                    name="System RAM",
                    passed=True,
                    message=f"{ram_gb:.1f}GB RAM ✓",
                    severity='info'
                ))
            
            # Check CPU
            cpu_cores = psutil.cpu_count(logical=False) or 1
            if cpu_cores < self.MIN_CPU_CORES:
                self.results.append(ValidationResult(
                    name="CPU Cores",
                    passed=False,
                    message=f"Only {cpu_cores} core(s)",
                    severity='warning',
                    suggested_fix="Performance may be limited with containers"
                ))
            else:
                self.results.append(ValidationResult(
                    name="CPU Cores",
                    passed=True,
                    message=f"{cpu_cores} cores ✓",
                    severity='info'
                ))
                
        except ImportError:
            self.results.append(ValidationResult(
                name="System Resources",
                passed=False,
                message="Cannot check (psutil not installed)",
                severity='warning',
                suggested_fix="Install psutil: pip install psutil"
            ))
    
    def check_sudo_access(self):
        """Check if sudo is available and passwordless."""
        try:
            result = subprocess.run(
                ['sudo', '-n', 'true'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                self.results.append(ValidationResult(
                    name="Sudo Access",
                    passed=True,
                    message="Passwordless sudo available ✓",
                    severity='info'
                ))
            else:
                self.results.append(ValidationResult(
                    name="Sudo Access",
                    passed=False,
                    message="Sudo requires password (will prompt when needed)",
                    severity='info',
                    suggested_fix="Run 'sudo -v' before starting to cache credentials"
                ))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.results.append(ValidationResult(
                name="Sudo Access",
                passed=False,
                message="Sudo not available or check failed",
                severity='warning',
                suggested_fix="Some installations require sudo access"
            ))
    
    def check_docker_availability(self):
        """Check if Docker is installed and running."""
        # Check if docker command exists
        docker_path = shutil.which('docker')
        if not docker_path:
            self.results.append(ValidationResult(
                name="Docker",
                passed=False,
                message="Docker not installed",
                severity='info',
                suggested_fix="Docker will be installed during setup if needed"
            ))
            return
        
        # Check if docker daemon is running
        try:
            result = subprocess.run(
                ['docker', 'info'],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                self.results.append(ValidationResult(
                    name="Docker",
                    passed=True,
                    message="Docker installed and running ✓",
                    severity='info'
                ))
            else:
                stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ""
                if 'permission denied' in stderr.lower():
                    self.results.append(ValidationResult(
                        name="Docker",
                        passed=False,
                        message="Docker installed but user lacks permissions",
                        severity='warning',
                        suggested_fix="User will be added to docker group during setup"
                    ))
                else:
                    self.results.append(ValidationResult(
                        name="Docker",
                        passed=False,
                        message="Docker installed but daemon not running",
                        severity='warning',
                        suggested_fix="Start Docker: sudo systemctl start docker"
                    ))
        except subprocess.TimeoutExpired:
            self.results.append(ValidationResult(
                name="Docker",
                passed=False,
                message="Docker check timed out",
                severity='warning',
                suggested_fix="Check Docker service status"
            ))
    
    def check_systemd_status(self):
        """Check if systemd is available (important for service management)."""
        try:
            result = subprocess.run(
                ['systemctl', '--version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                self.results.append(ValidationResult(
                    name="Systemd",
                    passed=True,
                    message="Systemd available ✓",
                    severity='info'
                ))
            else:
                self.results.append(ValidationResult(
                    name="Systemd",
                    passed=False,
                    message="Systemd not detected",
                    severity='warning',
                    suggested_fix="Some services may need manual startup on non-systemd systems"
                ))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.results.append(ValidationResult(
                name="Systemd",
                passed=False,
                message="Systemd not available",
                severity='warning',
                suggested_fix="Consider a systemd-based distribution for easier service management"
            ))
    
    def check_dns_configuration(self):
        """Check current DNS configuration (relevant for AdGuard)."""
        try:
            # Check if systemd-resolved is running (common conflict with AdGuard)
            result = subprocess.run(
                ['systemctl', 'is-active', 'systemd-resolved'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                self.results.append(ValidationResult(
                    name="DNS Configuration",
                    passed=False,
                    message="systemd-resolved is active (may conflict with AdGuard)",
                    severity='warning',
                    suggested_fix="AdGuard setup will handle this automatically"
                ))
            else:
                self.results.append(ValidationResult(
                    name="DNS Configuration",
                    passed=True,
                    message="No systemd-resolved conflict detected ✓",
                    severity='info'
                ))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.results.append(ValidationResult(
                name="DNS Configuration",
                passed=True,
                message="Could not check DNS configuration (non-critical)",
                severity='info'
            ))

    # ===== Extended Checks for Common Issues =====
    
    def check_docker_daemon_socket(self):
        """Check if Docker daemon socket is accessible (common permission issue)."""
        try:
            import subprocess
            result = subprocess.run(
                ['docker', 'ps'],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                self.results.append(ValidationResult(
                    name="Docker Socket Access",
                    passed=True,
                    message="Docker daemon socket accessible ✓",
                    severity='info'
                ))
            else:
                stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ""
                if 'permission denied' in stderr.lower() or 'dial unix' in stderr.lower():
                    self.results.append(ValidationResult(
                        name="Docker Socket Access",
                        passed=False,
                        message="Docker socket permission denied - user not in docker group",
                        severity='warning',
                        suggested_fix="Run: sudo usermod -aG docker $USER && newgrp docker (or log out/in)"
                    ))
                elif 'cannot connect' in stderr.lower():
                    self.results.append(ValidationResult(
                        name="Docker Socket Access",
                        passed=False,
                        message="Cannot connect to Docker daemon - service may not be running",
                        severity='error',
                        suggested_fix="Run: sudo systemctl start docker"
                    ))
                else:
                    self.results.append(ValidationResult(
                        name="Docker Socket Access",
                        passed=False,
                        message=f"Docker access issue: {stderr[:100]}",
                        severity='warning',
                        suggested_fix="Check Docker installation and service status"
                    ))
        except Exception as e:
            self.results.append(ValidationResult(
                name="Docker Socket Access",
                passed=False,
                message=f"Could not check Docker access: {e}",
                severity='info'
            ))

    def check_docker_storage_driver(self):
        """Check Docker storage driver for performance issues."""
        try:
            result = subprocess.run(
                ['docker', 'info', '--format', '{{.Driver}}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                driver = result.stdout.strip()
                if driver == 'overlay2':
                    self.results.append(ValidationResult(
                        name="Docker Storage Driver",
                        passed=True,
                        message=f"Using optimal storage driver: {driver} ✓",
                        severity='info'
                    ))
                elif driver in ['aufs', 'devicemapper']:
                    self.results.append(ValidationResult(
                        name="Docker Storage Driver",
                        passed=True,
                        message=f"Using legacy storage driver: {driver}",
                        severity='warning',
                        suggested_fix="Consider migrating to overlay2 for better performance"
                    ))
                else:
                    self.results.append(ValidationResult(
                        name="Docker Storage Driver",
                        passed=True,
                        message=f"Storage driver: {driver}",
                        severity='info'
                    ))
            else:
                self.results.append(ValidationResult(
                    name="Docker Storage Driver",
                    passed=False,
                    message="Could not determine Docker storage driver",
                    severity='info'
                ))
        except Exception:
            self.results.append(ValidationResult(
                name="Docker Storage Driver",
                passed=False,
                message="Could not check Docker storage driver",
                severity='info'
            ))

    def check_docker_network_conflicts(self):
        """Check for common Docker network conflicts."""
        conflicts = []
        
        try:
            # Check default bridge network
            result = subprocess.run(
                ['docker', 'network', 'ls', '--format', '{{.Name}}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                networks = result.stdout.strip().split('\n')
                
                # Check for potential subnet conflicts
                result2 = subprocess.run(
                    ['docker', 'network', 'inspect', 'bridge', '--format', '{{range .IPAM.Config}}{{.Subnet}}{{end}}'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result2.returncode == 0:
                    subnet = result2.stdout.strip()
                    # Common conflict: Docker using 172.17.0.0/16 when VPN uses it
                    if subnet.startswith('172.17'):
                        conflicts.append("Docker using 172.17.x.x which may conflict with some VPNs")
        except Exception:
            pass
        
        if conflicts:
            self.results.append(ValidationResult(
                name="Docker Network Conflicts",
                passed=False,
                message=f"; ".join(conflicts),
                severity='warning',
                suggested_fix="If using VPN, configure Docker daemon.json with custom bip address"
            ))
        else:
            self.results.append(ValidationResult(
                name="Docker Network Conflicts",
                passed=True,
                message="No obvious Docker network conflicts detected ✓",
                severity='info'
            ))

    def check_ssl_certificate_capability(self):
        """Check if the system can obtain SSL certificates."""
        issues = []
        
        # Check if ports 80/443 are available for Let's Encrypt
        for port in [80, 443]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('0.0.0.0', port))
                sock.close()
                if result == 0:
                    issues.append(f"Port {port} is in use (required for Let's Encrypt)")
            except (OSError, socket.error):
                pass
        
        # Check internet connectivity for ACME
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '3', 'acme-v02.api.letsencrypt.org'],
                capture_output=True,
                timeout=10
            )
            if result.returncode != 0:
                issues.append("Cannot reach Let's Encrypt API (acme-v02.api.letsencrypt.org)")
        except (subprocess.SubprocessError, OSError):
            issues.append("Could not verify Let's Encrypt connectivity")
        
        if issues:
            self.results.append(ValidationResult(
                name="SSL Certificate Capability",
                passed=False,
                message=f"Issues: {', '.join(issues[:2])}",
                severity='warning',
                suggested_fix="Free ports 80/443 or use DNS challenge for Let's Encrypt"
            ))
        else:
            self.results.append(ValidationResult(
                name="SSL Certificate Capability",
                passed=True,
                message="System can obtain SSL certificates via Let's Encrypt ✓",
                severity='info'
            ))

    def check_firewall_configuration(self):
        """Check firewall status and common issues."""
        try:
            # Check if UFW is installed and active
            result = subprocess.run(
                ['ufw', 'status'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                if 'Status: active' in result.stdout:
                    # Check if SSH is allowed (critical!)
                    if '22/tcp' not in result.stdout and 'OpenSSH' not in result.stdout:
                        self.results.append(ValidationResult(
                            name="Firewall Configuration",
                            passed=False,
                            message="UFW active but SSH (port 22) may be blocked!",
                            severity='critical',
                            suggested_fix="Run: sudo ufw allow 22/tcp before proceeding!"
                        ))
                    else:
                        self.results.append(ValidationResult(
                            name="Firewall Configuration",
                            passed=True,
                            message="UFW active with SSH allowed ✓",
                            severity='info'
                        ))
                else:
                    self.results.append(ValidationResult(
                        name="Firewall Configuration",
                        passed=True,
                        message="UFW installed but not active",
                        severity='info',
                        suggested_fix="Consider enabling: sudo ufw enable (after allowing SSH)"
                    ))
            else:
                # Check for iptables
                result2 = subprocess.run(['which', 'iptables'], capture_output=True)
                if result2.returncode == 0:
                    self.results.append(ValidationResult(
                        name="Firewall Configuration",
                        passed=True,
                        message="iptables available (no UFW wrapper)",
                        severity='info'
                    ))
                else:
                    self.results.append(ValidationResult(
                        name="Firewall Configuration",
                        passed=True,
                        message="No firewall detected",
                        severity='warning',
                        suggested_fix="Consider installing ufw for easier firewall management"
                    ))
        except Exception:
            self.results.append(ValidationResult(
                name="Firewall Configuration",
                passed=False,
                message="Could not check firewall status",
                severity='info'
            ))

    def check_port_forwarding_requirement(self, domain_config: Dict = None):
        """Check if port forwarding will be required."""
        if not domain_config:
            self.results.append(ValidationResult(
                name="Port Forwarding",
                passed=True,
                message="No external domain configured - local access only",
                severity='info'
            ))
            return
        
        if domain_config.get('use_tailscale_funnel'):
            self.results.append(ValidationResult(
                name="Port Forwarding",
                passed=True,
                message="Using Tailscale Funnel - no port forwarding needed ✓",
                severity='info'
            ))
        elif domain_config.get('expose_externally'):
            self.results.append(ValidationResult(
                name="Port Forwarding",
                passed=False,
                message="External access requires router port forwarding (80, 443)",
                severity='warning',
                suggested_fix="Configure your router to forward ports 80 and 443 to this server"
            ))
        else:
            self.results.append(ValidationResult(
                name="Port Forwarding",
                passed=True,
                message="Tailscale-only access - no port forwarding needed ✓",
                severity='info'
            ))

    def check_backup_destination(self, storage_path: str = None):
        """Check if backup destination is configured."""
        if not storage_path:
            storage_path = "~/.home-server-data"
        
        path = Path(storage_path).expanduser()
        backup_path = path / "backups"
        
        try:
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Check available space for backups
            stat = shutil.disk_usage(backup_path)
            free_gb = stat.free / (1024**3)
            
            if free_gb < 10:
                self.results.append(ValidationResult(
                    name="Backup Destination",
                    passed=False,
                    message=f"Only {free_gb:.1f}GB free for backups (recommend 10GB+)",
                    severity='warning',
                    suggested_fix="Free up space or configure external backup destination"
                ))
            else:
                self.results.append(ValidationResult(
                    name="Backup Destination",
                    passed=True,
                    message=f"Backup destination ready with {free_gb:.1f}GB available ✓",
                    severity='info'
                ))
        except Exception as e:
            self.results.append(ValidationResult(
                name="Backup Destination",
                passed=False,
                message=f"Could not configure backup destination: {e}",
                severity='warning',
                suggested_fix="Check permissions on storage path"
            ))

    def check_update_policy(self):
        """Check system's automatic update configuration."""
        try:
            # Check unattended-upgrades
            if Path('/etc/apt/apt.conf.d/20auto-upgrades').exists():
                with open('/etc/apt/apt.conf.d/20auto-upgrades', 'r') as f:
                    content = f.read()
                    if 'APT::Periodic::Unattended-Upgrade "1"' in content:
                        self.results.append(ValidationResult(
                            name="Automatic Updates",
                            passed=True,
                            message="Unattended upgrades enabled ✓",
                            severity='info'
                        ))
                    else:
                        self.results.append(ValidationResult(
                            name="Automatic Updates",
                            passed=True,
                            message="Unattended upgrades disabled",
                            severity='warning',
                            suggested_fix="Consider enabling: sudo apt install unattended-upgrades"
                        ))
            else:
                self.results.append(ValidationResult(
                    name="Automatic Updates",
                    passed=True,
                    message="Unattended upgrades not configured",
                    severity='info',
                    suggested_fix="Consider setting up automatic security updates"
                ))
        except Exception:
            self.results.append(ValidationResult(
                name="Automatic Updates",
                passed=False,
                message="Could not check update policy",
                severity='info'
            ))

    def check_timezone_configuration(self):
        """Check if timezone is properly configured."""
        try:
            result = subprocess.run(
                ['timedatectl', 'status'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                if 'UTC' in result.stdout and 'Time zone: Etc/UTC' in result.stdout:
                    self.results.append(ValidationResult(
                        name="Timezone Configuration",
                        passed=True,
                        message="Using UTC (may want to set local timezone)",
                        severity='info',
                        suggested_fix="Run: sudo timedatectl set-timezone Your/Timezone"
                    ))
                else:
                    self.results.append(ValidationResult(
                        name="Timezone Configuration",
                        passed=True,
                        message="Timezone configured ✓",
                        severity='info'
                    ))
            else:
                self.results.append(ValidationResult(
                    name="Timezone Configuration",
                    passed=False,
                    message="Could not verify timezone",
                    severity='info'
                ))
        except Exception:
            self.results.append(ValidationResult(
                name="Timezone Configuration",
                passed=False,
                message="timedatectl not available",
                severity='info'
            ))

    def check_log_rotation(self):
        """Check if log rotation is configured."""
        try:
            if Path('/etc/logrotate.d').exists():
                # Check if Docker log rotation is configured
                if Path('/etc/docker/daemon.json').exists():
                    with open('/etc/docker/daemon.json', 'r') as f:
                        config = f.read()
                        if 'log-opts' in config and 'max-size' in config:
                            self.results.append(ValidationResult(
                                name="Log Rotation",
                                passed=True,
                                message="Docker log rotation configured ✓",
                                severity='info'
                            ))
                        else:
                            self.results.append(ValidationResult(
                                name="Log Rotation",
                                passed=False,
                                message="Docker log rotation not configured",
                                severity='warning',
                                suggested_fix="Configure /etc/docker/daemon.json with log-opts max-size"
                            ))
                else:
                    self.results.append(ValidationResult(
                        name="Log Rotation",
                        passed=False,
                        message="Docker daemon.json not present",
                        severity='info',
                        suggested_fix="Will configure log rotation during setup"
                    ))
            else:
                self.results.append(ValidationResult(
                    name="Log Rotation",
                    passed=False,
                    message="Logrotate not found",
                    severity='info'
                ))
        except Exception:
            self.results.append(ValidationResult(
                name="Log Rotation",
                passed=False,
                message="Could not check log rotation",
                severity='info'
            ))

    def check_memory_swap(self):
        """Check if swap is configured (important for low-memory systems)."""
        try:
            result = subprocess.run(
                ['free', '-h'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if line.startswith('Swap:'):
                        parts = line.split()
                        if len(parts) >= 2:
                            swap_total = parts[1]
                            if swap_total == '0B' or swap_total == '0':
                                self.results.append(ValidationResult(
                                    name="Memory Swap",
                                    passed=False,
                                    message="No swap configured",
                                    severity='warning',
                                    suggested_fix="Create swap file: sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile"
                                ))
                            else:
                                self.results.append(ValidationResult(
                                    name="Memory Swap",
                                    passed=True,
                                    message=f"Swap configured: {swap_total} ✓",
                                    severity='info'
                                ))
                            break
            else:
                self.results.append(ValidationResult(
                    name="Memory Swap",
                    passed=False,
                    message="Could not check swap",
                    severity='info'
                ))
        except Exception:
            self.results.append(ValidationResult(
                name="Memory Swap",
                passed=False,
                message="Could not check swap configuration",
                severity='info'
            ))

    def check_kernel_version(self):
        """Check kernel version for compatibility issues."""
        try:
            result = subprocess.run(
                ['uname', '-r'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                # Parse major.minor version
                match = re.match(r'(\d+)\.(\d+)', version)
                if match:
                    major = int(match.group(1))
                    minor = int(match.group(2))
                    
                    if major < 4 or (major == 4 and minor < 9):
                        self.results.append(ValidationResult(
                            name="Kernel Version",
                            passed=False,
                            message=f"Kernel {version} is quite old",
                            severity='warning',
                            suggested_fix="Consider updating your system for better container support"
                        ))
                    else:
                        self.results.append(ValidationResult(
                            name="Kernel Version",
                            passed=True,
                            message=f"Kernel {version} ✓",
                            severity='info'
                        ))
                else:
                    self.results.append(ValidationResult(
                        name="Kernel Version",
                        passed=True,
                        message=f"Kernel {version}",
                        severity='info'
                    ))
        except Exception:
            self.results.append(ValidationResult(
                name="Kernel Version",
                passed=False,
                message="Could not check kernel version",
                severity='info'
            ))

    def check_apparmor_selinux(self):
        """Check AppArmor/SELinux status (can cause container issues)."""
        try:
            # Check AppArmor
            result = subprocess.run(
                ['aa-status'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                if 'profiles are in enforce mode' in result.stdout:
                    self.results.append(ValidationResult(
                        name="AppArmor/SELinux",
                        passed=True,
                        message="AppArmor is active (may need profiles for some containers)",
                        severity='info',
                        suggested_fix="If containers fail to start, check AppArmor logs: sudo dmesg | grep apparmor"
                    ))
                else:
                    self.results.append(ValidationResult(
                        name="AppArmor/SELinux",
                        passed=True,
                        message="AppArmor present but not enforcing ✓",
                        severity='info'
                    ))
            else:
                # Check for SELinux
                result2 = subprocess.run(['getenforce'], capture_output=True, text=True, timeout=5)
                if result2.returncode == 0:
                    mode = result2.stdout.strip()
                    if mode == 'Enforcing':
                        self.results.append(ValidationResult(
                            name="AppArmor/SELinux",
                            passed=True,
                            message="SELinux enforcing (may need policies for containers)",
                            severity='info',
                            suggested_fix="If containers fail, check: sudo ausearch -m avc -ts recent"
                        ))
                    else:
                        self.results.append(ValidationResult(
                            name="AppArmor/SELinux",
                            passed=True,
                            message=f"SELinux {mode} ✓",
                            severity='info'
                        ))
                else:
                    self.results.append(ValidationResult(
                        name="AppArmor/SELinux",
                        passed=True,
                        message="No MAC (AppArmor/SELinux) detected",
                        severity='info'
                    ))
        except Exception:
            self.results.append(ValidationResult(
                name="AppArmor/SELinux",
                passed=False,
                message="Could not check MAC status",
                severity='info'
            ))

    def check_disk_io_performance(self):
        """Quick disk I/O check for storage-heavy workloads."""
        try:
            # Check if we're on a network filesystem (NFS, CIFS, etc.)
            result = subprocess.run(
                ['df', '-T', '/'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 2:
                        fs_type = parts[1]
                        if fs_type in ['nfs', 'nfs4', 'cifs', 'smbfs']:
                            self.results.append(ValidationResult(
                                name="Disk I/O Performance",
                                passed=False,
                                message=f"Root filesystem is {fs_type} (network filesystem)",
                                severity='warning',
                                suggested_fix="Network filesystems may impact Docker performance. Consider local storage."
                            ))
                        elif fs_type in ['ext4', 'xfs', 'btrfs']:
                            self.results.append(ValidationResult(
                                name="Disk I/O Performance",
                                passed=True,
                                message=f"Using {fs_type} filesystem ✓",
                                severity='info'
                            ))
                        else:
                            self.results.append(ValidationResult(
                                name="Disk I/O Performance",
                                passed=True,
                                message=f"Filesystem type: {fs_type}",
                                severity='info'
                            ))
        except Exception:
            self.results.append(ValidationResult(
                name="Disk I/O Performance",
                passed=False,
                message="Could not check filesystem type",
                severity='info'
            ))


def run_preflight_checks(storage_path: str = None, domain_config: Dict = None, verbose: bool = True) -> bool:
    """Run all pre-flight checks and return True if installation can proceed."""
    validator = PreflightValidator()
    results = validator.run_all_checks(storage_path, domain_config)
    
    if verbose:
        print("\n🔍 Pre-flight System Checks")
        print("=" * 50)
        
        for result in results:
            emoji = {
                'info': '✓' if result.passed else 'ℹ️',
                'warning': '⚠️',
                'error': '❌',
                'critical': '🚫'
            }.get(result.severity, '?')
            
            print(f"  {emoji} {result.name}: {result.message}")
            if not result.passed and result.suggested_fix:
                print(f"     💡 {result.suggested_fix}")
        
        passed, warnings, errors = validator.get_summary()
        print("-" * 50)
        print(f"  Passed: {passed}, Warnings: {warnings}, Errors: {errors}")
        print()
    
    return not validator.has_blocking_issues()


if __name__ == "__main__":
    can_proceed = run_preflight_checks()
    print(f"\nCan proceed with installation: {'Yes' if can_proceed else 'No'}")

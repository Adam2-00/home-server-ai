"""
Hardware Detection Module
Detects CPU, RAM, disk space, network interfaces, and Linux distro.
"""
try:
    import psutil
except ImportError:
    psutil = None

import platform
import subprocess
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class HardwareProfile:
    """Structured hardware profile for planning engine."""
    cpu_cores: int
    cpu_threads: int
    cpu_model: str
    ram_gb: float
    disk_gb: Dict[str, float]  # mount point -> free GB
    network_interfaces: List[Dict]
    distro: str
    distro_version: str
    architecture: str
    has_docker: bool
    has_docker_compose: bool
    has_curl: bool
    has_systemd: bool
    potential_issues: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class HardwareDetector:
    """Detects system hardware and compatibility."""

    def __init__(self):
        self.issues: List[str] = []

    def detect(self) -> HardwareProfile:
        """Run full hardware detection."""
        self.issues = []

        profile = HardwareProfile(
            cpu_cores=self._get_cpu_cores(),
            cpu_threads=self._get_cpu_threads(),
            cpu_model=self._get_cpu_model(),
            ram_gb=self._get_ram_gb(),
            disk_gb=self._get_disk_space(),
            network_interfaces=self._get_network_interfaces(),
            distro=self._get_distro(),
            distro_version=self._get_distro_version(),
            architecture=self._get_architecture(),
            has_docker=self._check_docker(),
            has_docker_compose=self._check_docker_compose(),
            has_curl=self._check_curl(),
            has_systemd=self._check_systemd(),
            potential_issues=self.issues
        )

        self._validate_profile(profile)
        return profile

    def _get_cpu_cores(self) -> int:
        if psutil:
            return psutil.cpu_count(logical=False) or 1
        return 1

    def _get_cpu_threads(self) -> int:
        if psutil:
            return psutil.cpu_count(logical=True) or 1
        return 1

    def _get_cpu_model(self) -> str:
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'model name' in line:
                        return line.split(':')[1].strip()
        except (IOError, OSError, PermissionError):
            pass
        return platform.processor() or "Unknown"

    def _get_ram_gb(self) -> float:
        if psutil:
            mem = psutil.virtual_memory()
            return round(mem.total / (1024**3), 2)
        return 0.0

    def _get_disk_space(self) -> Dict[str, float]:
        disks = {}
        if psutil:
            for part in psutil.disk_partitions():
                if part.fstype and not part.mountpoint.startswith('/snap'):
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        disks[part.mountpoint] = round(usage.free / (1024**3), 2)
                    except (OSError, PermissionError, ValueError):
                        pass
        return disks

    def _get_network_interfaces(self) -> List[Dict]:
        interfaces = []
        if psutil:
            try:
                stats = psutil.net_if_addrs()
                for name, addrs in stats.items():
                    iface_info = {"name": name, "addresses": []}
                    for addr in addrs:
                        if addr.family.name in ['AF_INET', 'AF_INET6']:
                            iface_info["addresses"].append({
                                "type": addr.family.name,
                                "address": addr.address
                            })
                    interfaces.append(iface_info)
            except (OSError, AttributeError):
                pass
        return interfaces

    def _get_distro(self) -> str:
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('ID='):
                        return line.split('=')[1].strip().strip('"')
        except (IOError, OSError, PermissionError):
            pass
        return "unknown"

    def _get_distro_version(self) -> str:
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('VERSION_ID='):
                        return line.split('=')[1].strip().strip('"')
        except (IOError, OSError, PermissionError):
            pass
        return "unknown"

    def _get_architecture(self) -> str:
        return platform.machine()

    def _check_docker(self) -> bool:
        try:
            subprocess.run(['docker', '--version'], capture_output=True, check=True, timeout=5)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            self.issues.append("Docker not installed - will need to install")
            return False

    def _check_docker_compose(self) -> bool:
        try:
            # Check for docker compose plugin
            result = subprocess.run(['docker', 'compose', 'version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                return True
            # Check for standalone docker-compose
            result = subprocess.run(['docker-compose', '--version'], capture_output=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.issues.append("Docker Compose not found - will install")
            return False

    def _check_curl(self) -> bool:
        try:
            subprocess.run(['curl', '--version'], capture_output=True, check=True, timeout=5)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            self.issues.append("curl not installed - will need to install")
            return False

    def _check_systemd(self) -> bool:
        try:
            result = subprocess.run(['systemctl', '--version'], capture_output=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.issues.append("systemd not detected - some services may need manual management")
            return False

    def _validate_profile(self, profile: HardwareProfile):
        """Check for potential issues and add to issues list."""
        # RAM check
        if profile.ram_gb < 2:
            self.issues.append(f"Low RAM ({profile.ram_gb}GB) - may struggle with media servers")

        # Disk check
        root_free = profile.disk_gb.get('/', 0)
        if root_free < 10:
            self.issues.append(f"Low disk space on root ({root_free}GB free) - recommend 20GB+")

        # CPU check
        if profile.cpu_cores < 2:
            self.issues.append("Single-core CPU - performance may be limited")

        # Distro compatibility
        supported = ['ubuntu', 'debian', 'linuxmint', 'pop']
        if profile.distro not in supported:
            self.issues.append(f"Distro '{profile.distro}' not fully tested - may need manual adjustments")


def detect_hardware() -> HardwareProfile:
    """Convenience function to detect hardware."""
    detector = HardwareDetector()
    return detector.detect()


if __name__ == "__main__":
    profile = detect_hardware()
    print(profile.to_json())

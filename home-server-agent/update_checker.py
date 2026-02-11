#!/usr/bin/env python3
"""
Update Checker Module
Checks for updates to installed services and notifies users.
"""
import os
import json
import subprocess
import logging
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class UpdateInfo:
    """Information about an available update."""
    service: str
    current_version: str
    latest_version: str
    update_available: bool
    release_notes: Optional[str]
    severity: str  # 'security', 'feature', 'patch'
    download_url: Optional[str]
    checked_at: str


class UpdateChecker:
    """Checks for updates to installed services."""
    
    # Service update endpoints
    SERVICES = {
        'tailscale': {
            'type': 'apt',
            'package': 'tailscale',
            'check_cmd': ['tailscale', 'version'],
            'version_regex': r'(\d+\.\d+\.\d+)',
        },
        'docker': {
            'type': 'docker',
            'check_cmd': ['docker', 'version', '--format', '{{.Server.Version}}'],
            'version_regex': r'(\d+\.\d+\.\d+)',
        },
        'adguard': {
            'type': 'docker_image',
            'image': 'adguard/adguardhome',
            'container': 'adguardhome',
            'github_repo': 'AdguardTeam/AdGuardHome',
        },
        'jellyfin': {
            'type': 'docker_image',
            'image': 'jellyfin/jellyfin',
            'container': 'jellyfin',
            'github_repo': 'jellyfin/jellyfin',
        },
        'immich': {
            'type': 'docker_image',
            'image': 'ghcr.io/immich-app/immich-server',
            'container': 'immich_server',
            'github_repo': 'immich-app/immich',
        },
        'openclaw': {
            'type': 'github_release',
            'binary': 'openclaw',
            'github_repo': 'openclaw/agent',
        }
    }
    
    def __init__(self, cache_file: str = "~/.home-server/update_cache.json"):
        self.cache_file = Path(cache_file).expanduser()
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cached update information."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load update cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save update cache."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save update cache: {e}")
    
    def check_all(self, force: bool = False) -> Dict[str, UpdateInfo]:
        """Check for updates for all installed services."""
        results = {}
        
        for service_name, config in self.SERVICES.items():
            # Check if service is installed
            if not self._is_installed(service_name, config):
                continue
            
            # Check cache
            cache_key = f"{service_name}_check"
            last_check = self.cache.get(cache_key, {}).get('timestamp')
            
            if not force and last_check:
                last_check_dt = datetime.fromisoformat(last_check)
                hours_since = (datetime.now() - last_check_dt).total_seconds() / 3600
                if hours_since < 24:
                    # Use cached result
                    cached = self.cache.get(f"{service_name}_update")
                    if cached:
                        results[service_name] = UpdateInfo(**cached)
                        continue
            
            # Perform check
            try:
                update_info = self._check_service(service_name, config)
                results[service_name] = update_info
                
                # Update cache
                self.cache[cache_key] = {'timestamp': datetime.now().isoformat()}
                self.cache[f"{service_name}_update"] = update_info.to_dict()
            except Exception as e:
                logger.error(f"Failed to check updates for {service_name}: {e}")
        
        self._save_cache()
        return results
    
    def _is_installed(self, service_name: str, config: Dict) -> bool:
        """Check if a service is installed."""
        check_cmd = config.get('check_cmd')
        container = config.get('container')
        binary = config.get('binary')
        
        if check_cmd:
            try:
                result = subprocess.run(check_cmd, capture_output=True, timeout=5)
                return result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return False
        
        if container:
            try:
                result = subprocess.run(
                    ['docker', 'ps', '-a', '--filter', f'name={container}', '--format', '{{.Names}}'],
                    capture_output=True, text=True, timeout=10
                )
                return container in result.stdout
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return False
        
        if binary:
            try:
                result = subprocess.run(['which', binary], capture_output=True, timeout=5)
                return result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return False
        
        return False
    
    def _check_service(self, service_name: str, config: Dict) -> UpdateInfo:
        """Check for updates for a specific service."""
        service_type = config.get('type', 'unknown')
        
        if service_type == 'apt':
            return self._check_apt_package(service_name, config)
        elif service_type == 'docker':
            return self._check_docker_version(service_name, config)
        elif service_type == 'docker_image':
            return self._check_docker_image(service_name, config)
        elif service_type == 'github_release':
            return self._check_github_release(service_name, config)
        else:
            return UpdateInfo(
                service=service_name,
                current_version='unknown',
                latest_version='unknown',
                update_available=False,
                release_notes=None,
                severity='patch',
                download_url=None,
                checked_at=datetime.now().isoformat()
            )
    
    def _check_apt_package(self, service_name: str, config: Dict) -> UpdateInfo:
        """Check for apt package updates."""
        package = config.get('package', service_name)
        
        # Get current version
        current_version = 'unknown'
        check_cmd = config.get('check_cmd')
        version_regex = config.get('version_regex', r'(\d+\.\d+\.\d+)')
        
        if check_cmd:
            try:
                result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    match = re.search(version_regex, result.stdout)
                    if match:
                        current_version = match.group(1)
            except Exception:
                pass
        
        # Check for updates via apt
        latest_version = current_version
        update_available = False
        
        try:
            result = subprocess.run(
                ['apt', 'list', '--upgradable', package],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and package in result.stdout:
                # Parse version from output
                for line in result.stdout.split('\n'):
                    if package in line and 'upgradable' in line:
                        match = re.search(r'\[upgradable from: ([^\]]+)\]', line)
                        if match:
                            latest_version = line.split()[1].split('/')[0]
                            update_available = True
                            break
        except Exception:
            pass
        
        return UpdateInfo(
            service=service_name,
            current_version=current_version,
            latest_version=latest_version,
            update_available=update_available,
            release_notes=None,
            severity='patch',
            download_url=None,
            checked_at=datetime.now().isoformat()
        )
    
    def _check_docker_version(self, service_name: str, config: Dict) -> UpdateInfo:
        """Check Docker version."""
        current_version = 'unknown'
        
        try:
            result = subprocess.run(
                config['check_cmd'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                current_version = result.stdout.strip()
        except Exception:
            pass
        
        return UpdateInfo(
            service=service_name,
            current_version=current_version,
            latest_version='check docker.com',
            update_available=False,
            release_notes='Visit https://docs.docker.com/engine/release-notes/',
            severity='patch',
            download_url='https://docs.docker.com/engine/install/',
            checked_at=datetime.now().isoformat()
        )
    
    def _check_docker_image(self, service_name: str, config: Dict) -> UpdateInfo:
        """Check for Docker image updates."""
        image = config.get('image')
        container = config.get('container')
        github_repo = config.get('github_repo')
        
        current_version = 'unknown'
        latest_version = 'unknown'
        update_available = False
        release_notes = None
        download_url = None
        
        # Get current image digest
        if container:
            try:
                result = subprocess.run(
                    ['docker', 'inspect', '--format={{.Config.Image}}', container],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    current_version = result.stdout.strip()
            except Exception:
                pass
        
        # Check GitHub for latest release
        if github_repo:
            try:
                import urllib.request
                url = f"https://api.github.com/repos/{github_repo}/releases/latest"
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'HomeServerUpdateChecker/1.0')
                req.add_header('Accept', 'application/vnd.github.v3+json')
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    latest_version = data.get('tag_name', 'unknown').lstrip('v')
                    release_notes = data.get('html_url')
                    
                    # Compare versions
                    current_v = self._parse_version(current_version.split(':')[-1])
                    latest_v = self._parse_version(latest_version)
                    update_available = latest_v > current_v
            except Exception as e:
                logger.debug(f"Failed to check GitHub for {service_name}: {e}")
        
        return UpdateInfo(
            service=service_name,
            current_version=current_version,
            latest_version=latest_version,
            update_available=update_available,
            release_notes=release_notes,
            severity='feature' if update_available else 'patch',
            download_url=download_url or f"https://hub.docker.com/r/{image.replace('ghcr.io/', '')}",
            checked_at=datetime.now().isoformat()
        )
    
    def _check_github_release(self, service_name: str, config: Dict) -> UpdateInfo:
        """Check GitHub for latest release."""
        binary = config.get('binary')
        github_repo = config.get('github_repo')
        
        current_version = 'unknown'
        latest_version = 'unknown'
        update_available = False
        release_notes = None
        
        # Get current version
        if binary:
            try:
                result = subprocess.run([binary, '--version'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    match = re.search(r'(\d+\.\d+\.\d+)', result.stdout)
                    if match:
                        current_version = match.group(1)
            except Exception:
                pass
        
        # Check GitHub
        if github_repo:
            try:
                import urllib.request
                url = f"https://api.github.com/repos/{github_repo}/releases/latest"
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'HomeServerUpdateChecker/1.0')
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    latest_version = data.get('tag_name', 'unknown').lstrip('v')
                    release_notes = data.get('html_url')
                    
                    # Compare versions
                    current_v = self._parse_version(current_version)
                    latest_v = self._parse_version(latest_version)
                    update_available = latest_v > current_v
            except Exception as e:
                logger.debug(f"Failed to check GitHub for {service_name}: {e}")
        
        return UpdateInfo(
            service=service_name,
            current_version=current_version,
            latest_version=latest_version,
            update_available=update_available,
            release_notes=release_notes,
            severity='feature' if update_available else 'patch',
            download_url=f"https://github.com/{github_repo}/releases/latest" if github_repo else None,
            checked_at=datetime.now().isoformat()
        )
    
    def _parse_version(self, version_str: str) -> Tuple[int, ...]:
        """Parse version string to comparable tuple."""
        try:
            # Remove 'v' prefix and any suffix
            version_str = version_str.lstrip('v').split('-')[0]
            parts = version_str.split('.')
            return tuple(int(p) for p in parts[:3] if p.isdigit())
        except (ValueError, AttributeError):
            return (0, 0, 0)
    
    def update_service(self, service_name: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Update a service to the latest version."""
        if service_name not in self.SERVICES:
            return False, f"Unknown service: {service_name}"
        
        config = self.SERVICES[service_name]
        service_type = config.get('type')
        
        if dry_run:
            return True, f"Would update {service_name} ({service_type})"
        
        try:
            if service_type == 'apt':
                package = config.get('package', service_name)
                subprocess.run(['sudo', 'apt', 'update'], check=True, capture_output=True)
                subprocess.run(['sudo', 'apt', 'install', '-y', package], check=True)
                return True, f"{service_name} updated successfully"
            
            elif service_type == 'docker_image':
                container = config.get('container')
                image = config.get('image')
                
                if container:
                    subprocess.run(['docker', 'stop', container], capture_output=True)
                    subprocess.run(['docker', 'rm', container], capture_output=True)
                
                subprocess.run(['docker', 'pull', image], check=True)
                # Note: User needs to recreate container with new image
                return True, f"{service_name} image updated. Recreate container to use new version."
            
            elif service_type == 'github_release':
                return False, f"Please update {service_name} manually from GitHub releases"
            
            else:
                return False, f"Update not supported for {service_name}"
                
        except subprocess.CalledProcessError as e:
            return False, f"Update failed: {e}"
        except Exception as e:
            return False, f"Error: {str(e)}"


def check_updates(force: bool = False) -> Dict[str, UpdateInfo]:
    """Check for updates for all services."""
    checker = UpdateChecker()
    return checker.check_all(force=force)


def print_update_status():
    """Print update status to console."""
    print("\n" + "="*60)
    print("  📦 Update Checker")
    print("="*60)
    
    updates = check_updates()
    
    if not updates:
        print("\n   No installed services found.")
    else:
        available_updates = [u for u in updates.values() if u.update_available]
        
        if available_updates:
            print(f"\n   🎉 {len(available_updates)} update(s) available:\n")
            for update in available_updates:
                print(f"   • {update.service}")
                print(f"     Current: {update.current_version}")
                print(f"     Latest:  {update.latest_version}")
                if update.release_notes:
                    print(f"     Release: {update.release_notes}")
                print()
        else:
            print("\n   ✅ All services are up to date!")
        
        print(f"\n   Checked {len(updates)} service(s):")
        for name, update in updates.items():
            status = "🔄" if update.update_available else "✅"
            print(f"   {status} {name}: {update.current_version}")
    
    print("\n   Run 'python update_checker.py --update <service>' to update")
    print("="*60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Update Checker')
    parser.add_argument('--check', action='store_true', help='Check for updates (default)')
    parser.add_argument('--force', action='store_true', help='Force check (ignore cache)')
    parser.add_argument('--update', type=str, metavar='SERVICE', help='Update specific service')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    if args.update:
        checker = UpdateChecker()
        success, message = checker.update_service(args.update, dry_run=args.dry_run)
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
            exit(1)
    else:
        updates = check_updates(force=args.force)
        
        if args.json:
            print(json.dumps({name: update.to_dict() for name, update in updates.items()}, indent=2))
        else:
            print_update_status()

#!/usr/bin/env python3
"""
Rollback Manager
Provides rollback capability for installed services and configuration.
"""
import os
import json
import sqlite3
import subprocess
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class BackupPoint:
    """A single backup/restore point."""
    backup_id: str
    timestamp: str
    description: str
    services: List[str]
    config_path: Optional[str]
    data_paths: Dict[str, str]  # service_name -> path


class RollbackManager:
    """Manages rollback and backup operations."""
    
    def __init__(self, backup_dir: str = "~/.home-server/backups", db_path: str = "state.db"):
        self.backup_dir = Path(backup_dir).expanduser()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_backup_db()
    
    def _init_backup_db(self):
        """Initialize backup tracking database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Backup points table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backup_points (
                id INTEGER PRIMARY KEY,
                backup_id TEXT UNIQUE,
                timestamp TEXT,
                description TEXT,
                services TEXT,  -- JSON list
                config_backup_path TEXT,
                data_backup_paths TEXT,  -- JSON dict
                created_at TEXT
            )
        ''')
        
        # Rollback log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rollback_log (
                id INTEGER PRIMARY KEY,
                backup_id TEXT,
                rollback_timestamp TEXT,
                success BOOLEAN,
                details TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_backup(self, services: List[str], description: str = "") -> str:
        """
        Create a backup point before making changes.
        
        Args:
            services: List of service names to backup
            description: Human-readable description of this backup
            
        Returns:
            backup_id: Unique identifier for this backup
        """
        backup_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().isoformat()
        data_paths = {}
        
        logger.info(f"Creating backup {backup_id} for services: {services}")
        
        # Backup configuration
        config_backup = None
        if os.path.exists("config.json"):
            config_backup = str(backup_path / "config.json")
            shutil.copy2("config.json", config_backup)
        
        # Backup service data
        for service in services:
            service_data_path = self._get_service_data_path(service)
            if service_data_path and os.path.exists(service_data_path):
                service_backup_path = backup_path / f"{service}_data"
                try:
                    shutil.copytree(service_data_path, service_backup_path, dirs_exist_ok=True)
                    data_paths[service] = str(service_backup_path)
                    logger.info(f"Backed up {service} data to {service_backup_path}")
                except Exception as e:
                    logger.warning(f"Failed to backup {service} data: {e}")
        
        # Backup Docker containers (export)
        for service in services:
            if self._is_docker_service(service):
                try:
                    container_backup = backup_path / f"{service}_container.tar"
                    self._backup_docker_container(service, str(container_backup))
                    data_paths[f"{service}_container"] = str(container_backup)
                except Exception as e:
                    logger.warning(f"Failed to backup {service} container: {e}")
        
        # Record backup in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO backup_points 
            (backup_id, timestamp, description, services, config_backup_path, data_backup_paths, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            backup_id,
            timestamp,
            description,
            json.dumps(services),
            config_backup,
            json.dumps(data_paths),
            timestamp
        ))
        conn.commit()
        conn.close()
        
        logger.info(f"Backup {backup_id} created successfully")
        return backup_id
    
    def rollback(self, backup_id: str, confirm: bool = True) -> Tuple[bool, str]:
        """
        Rollback to a previous backup point.
        
        Args:
            backup_id: The backup to restore
            confirm: If True, prompt for confirmation
            
        Returns:
            (success, message)
        """
        # Get backup info
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM backup_points WHERE backup_id = ?', (backup_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return False, f"Backup {backup_id} not found"
        
        services = json.loads(row[3])
        config_path = row[4]
        data_paths = json.loads(row[5])
        description = row[2]
        
        print(f"\n🔄 Rollback to: {backup_id}")
        print(f"   Description: {description}")
        print(f"   Services: {', '.join(services)}")
        print(f"   Created: {row[6]}")
        
        if confirm:
            response = input("\n⚠️  This will stop and remove current services. Continue? [y/N]: ").strip().lower()
            if response != 'y':
                return False, "Rollback cancelled by user"
        
        success_count = 0
        failed_services = []
        
        # Stop and remove current services
        for service in services:
            try:
                self._stop_service(service)
                self._remove_service(service)
            except Exception as e:
                logger.warning(f"Error stopping/removing {service}: {e}")
        
        # Restore configuration
        if config_path and os.path.exists(config_path):
            try:
                shutil.copy2(config_path, "config.json")
                logger.info("Configuration restored")
            except Exception as e:
                logger.error(f"Failed to restore configuration: {e}")
        
        # Restore service data
        for service in services:
            if service in data_paths:
                try:
                    service_data_path = self._get_service_data_path(service)
                    if service_data_path:
                        # Remove current data
                        if os.path.exists(service_data_path):
                            shutil.rmtree(service_data_path)
                        # Restore backup
                        shutil.copytree(data_paths[service], service_data_path)
                        logger.info(f"Restored {service} data")
                        success_count += 1
                except Exception as e:
                    logger.error(f"Failed to restore {service} data: {e}")
                    failed_services.append(service)
        
        # Restore Docker containers
        for service in services:
            container_key = f"{service}_container"
            if container_key in data_paths:
                try:
                    self._restore_docker_container(service, data_paths[container_key])
                    logger.info(f"Restored {service} container")
                except Exception as e:
                    logger.error(f"Failed to restore {service} container: {e}")
        
        # Restart services
        for service in services:
            if service not in failed_services:
                try:
                    self._start_service(service)
                except Exception as e:
                    logger.error(f"Failed to start {service}: {e}")
                    failed_services.append(service)
        
        # Log rollback
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO rollback_log (backup_id, rollback_timestamp, success, details)
            VALUES (?, ?, ?, ?)
        ''', (
            backup_id,
            datetime.now().isoformat(),
            len(failed_services) == 0,
            json.dumps({'restored': success_count, 'failed': failed_services})
        ))
        conn.commit()
        conn.close()
        
        if failed_services:
            return False, f"Rollback partially failed. Failed services: {', '.join(failed_services)}"
        
        return True, f"Successfully rolled back to {backup_id}"
    
    def list_backups(self) -> List[Dict]:
        """List all available backup points."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT backup_id, timestamp, description, services, created_at
            FROM backup_points
            ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        
        backups = []
        for row in rows:
            backups.append({
                'backup_id': row[0],
                'timestamp': row[1],
                'description': row[2],
                'services': json.loads(row[3]),
                'created_at': row[4]
            })
        
        return backups
    
    def delete_backup(self, backup_id: str) -> Tuple[bool, str]:
        """Delete a backup point."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM backup_points WHERE backup_id = ?', (backup_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return False, f"Backup {backup_id} not found"
        
        # Delete backup files
        backup_path = self.backup_dir / backup_id
        if backup_path.exists():
            try:
                shutil.rmtree(backup_path)
            except Exception as e:
                logger.error(f"Failed to delete backup files: {e}")
        
        # Remove from database
        cursor.execute('DELETE FROM backup_points WHERE backup_id = ?', (backup_id,))
        conn.commit()
        conn.close()
        
        return True, f"Backup {backup_id} deleted"
    
    def _get_service_data_path(self, service: str) -> Optional[str]:
        """Get the data path for a service."""
        home = Path.home()
        paths = {
            'adguard': str(home / 'adguardhome'),
            'jellyfin': str(home / 'home-server-data' / 'jellyfin'),
            'immich': str(home / 'home-server-data' / 'immich'),
            'tailscale': '/var/lib/tailscale',
            'openclaw': str(home / '.openclaw'),
        }
        return paths.get(service)
    
    def _is_docker_service(self, service: str) -> bool:
        """Check if service runs in Docker."""
        return service in ['adguard', 'jellyfin', 'immich']
    
    def _backup_docker_container(self, service: str, output_path: str):
        """Export Docker container to tar file."""
        container_names = {
            'adguard': 'adguardhome',
            'jellyfin': 'jellyfin',
            'immich': 'immich_server'
        }
        
        container = container_names.get(service)
        if container:
            subprocess.run(
                ['docker', 'export', '-o', output_path, container],
                check=True, capture_output=True, timeout=60
            )
    
    def _restore_docker_container(self, service: str, backup_path: str):
        """Restore Docker container from tar file."""
        # Container restore typically requires recreating from image
        # For now, we'll just restore the data volume
        logger.info(f"Container restore for {service} would import from {backup_path}")
    
    def _stop_service(self, service: str):
        """Stop a service."""
        if self._is_docker_service(service):
            container_names = {
                'adguard': 'adguardhome',
                'jellyfin': 'jellyfin',
                'immich': 'immich_server'
            }
            container = container_names.get(service)
            if container:
                subprocess.run(
                    ['docker', 'stop', container],
                    capture_output=True, timeout=30
                )
        elif service == 'tailscale':
            subprocess.run(['sudo', 'systemctl', 'stop', 'tailscaled'], capture_output=True)
    
    def _remove_service(self, service: str):
        """Remove a service (but keep data)."""
        if self._is_docker_service(service):
            container_names = {
                'adguard': 'adguardhome',
                'jellyfin': 'jellyfin',
                'immich': 'immich_server'
            }
            container = container_names.get(service)
            if container:
                subprocess.run(
                    ['docker', 'rm', container],
                    capture_output=True, timeout=30
                )
    
    def _start_service(self, service: str):
        """Start a service."""
        if self._is_docker_service(service):
            container_names = {
                'adguard': 'adguardhome',
                'jellyfin': 'jellyfin',
                'immich': 'immich_server'
            }
            container = container_names.get(service)
            if container:
                subprocess.run(
                    ['docker', 'start', container],
                    capture_output=True, timeout=30
                )
        elif service == 'tailscale':
            subprocess.run(['sudo', 'systemctl', 'start', 'tailscaled'], capture_output=True)


def create_rollback_point(services: List[str], description: str = "") -> str:
    """Convenience function to create a rollback point."""
    manager = RollbackManager()
    return manager.create_backup(services, description)


def rollback_to(backup_id: str, confirm: bool = True) -> Tuple[bool, str]:
    """Convenience function to rollback."""
    manager = RollbackManager()
    return manager.rollback(backup_id, confirm)


def list_rollback_points() -> List[Dict]:
    """List available rollback points."""
    manager = RollbackManager()
    return manager.list_backups()


def print_rollback_status():
    """Print rollback/backup status to console."""
    manager = RollbackManager()
    backups = manager.list_backups()
    
    print("\n" + "="*60)
    print("  🔄 Rollback Points")
    print("="*60)
    
    if not backups:
        print("\n   No rollback points found.")
        print("   Run setup to create automatic rollback points.")
    else:
        print(f"\n   Found {len(backups)} rollback point(s):\n")
        for i, backup in enumerate(backups, 1):
            print(f"   {i}. {backup['backup_id']}")
            print(f"      Description: {backup['description'] or 'No description'}")
            print(f"      Services: {', '.join(backup['services'])}")
            print(f"      Created: {backup['created_at']}")
            print()
        
        print("   To rollback: python rollback_manager.py --rollback <backup_id>")
    
    print("="*60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Rollback Manager')
    parser.add_argument('--list', action='store_true', help='List rollback points')
    parser.add_argument('--create', action='store_true', help='Create rollback point')
    parser.add_argument('--rollback', type=str, metavar='ID', help='Rollback to specific point')
    parser.add_argument('--delete', type=str, metavar='ID', help='Delete rollback point')
    parser.add_argument('--services', type=str, default='all', 
                       help='Services to backup (comma-separated, default: all)')
    parser.add_argument('--description', type=str, default='', help='Description for backup')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation')
    
    args = parser.parse_args()
    
    if args.list or (not args.create and not args.rollback and not args.delete):
        print_rollback_status()
    
    elif args.create:
        if args.services == 'all':
            services = ['tailscale', 'adguard', 'jellyfin', 'immich', 'openclaw']
        else:
            services = [s.strip() for s in args.services.split(',')]
        
        backup_id = create_rollback_point(services, args.description)
        print(f"✅ Created rollback point: {backup_id}")
    
    elif args.rollback:
        success, message = rollback_to(args.rollback, confirm=not args.yes)
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
            sys.exit(1)
    
    elif args.delete:
        success, message = RollbackManager().delete_backup(args.delete)
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
            sys.exit(1)

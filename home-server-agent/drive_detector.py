"""
External Drive Detection Module
Detects and helps configure external storage drives.
"""
import os
import re
import subprocess
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class StorageDevice:
    """Represents a storage device."""
    device: str  # /dev/sda1, /dev/nvme0n1p1
    mount_point: Optional[str]  # /mnt/storage, /media/usb
    size_gb: float
    used_gb: float
    free_gb: float
    filesystem: str  # ext4, ntfs, exfat
    label: Optional[str]  # "My Passport", "Backup"
    is_removable: bool
    is_mounted: bool
    
    @property
    def display_name(self) -> str:
        """Human-readable device name."""
        name = self.label or os.path.basename(self.device)
        mount_info = f" at {self.mount_point}" if self.mount_point else " (not mounted)"
        return f"{name} ({self.size_gb:.1f} GB){mount_info}"
    
    @property
    def is_available_for_use(self) -> bool:
        """Check if device can be used for storage."""
        # Must be mounted or mountable
        # Must have reasonable free space (>1GB)
        # Not the root filesystem
        if self.free_gb < 1.0:
            return False
        if self.mount_point == "/":
            return False
        return True


class DriveDetector:
    """Detects and manages external storage drives."""
    
    def __init__(self):
        self.devices: List[StorageDevice] = []
    
    def detect_drives(self) -> List[StorageDevice]:
        """Detect all storage devices."""
        self.devices = []
        
        try:
            # Get block devices with info
            result = subprocess.run(
                ["lsblk", "-J", "-o", "NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT,TYPE,ROTA"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return self._fallback_detection()
            
            import json
            data = json.loads(result.stdout)
            
            for device in data.get("blockdevices", []):
                # Skip disk-level entries, only get partitions
                if device.get("type") != "part":
                    continue
                
                device_path = f"/dev/{device.get('name', '')}"
                
                # Parse size (could be in G, T, M)
                size_str = device.get("size", "0G")
                size_gb = self._parse_size(size_str)
                
                # Get filesystem usage
                used_gb, free_gb = self._get_usage(device_path, device.get("mountpoint"))
                
                # Check if removable (rotational = 0 usually means SSD/NVMe, not necessarily removable)
                # Better check: look in /sys/block/ for removable attribute
                is_removable = self._is_removable_device(device.get("name", ""))
                
                storage = StorageDevice(
                    device=device_path,
                    mount_point=device.get("mountpoint"),
                    size_gb=size_gb,
                    used_gb=used_gb,
                    free_gb=free_gb,
                    filesystem=device.get("fstype") or "unknown",
                    label=device.get("label"),
                    is_removable=is_removable,
                    is_mounted=device.get("mountpoint") is not None
                )
                
                self.devices.append(storage)
            
        except Exception as e:
            print(f"Warning: Drive detection failed: {e}")
            return self._fallback_detection()
        
        return self.devices
    
    def get_available_drives(self) -> List[StorageDevice]:
        """Get drives available for use as storage."""
        if not self.devices:
            self.detect_drives()
        return [d for d in self.devices if d.is_available_for_use]
    
    def get_removable_drives(self) -> List[StorageDevice]:
        """Get removable/external drives."""
        if not self.devices:
            self.detect_drives()
        return [d for d in self.devices if d.is_removable and d.is_available_for_use]
    
    def suggest_storage_location(self) -> Optional[str]:
        """Suggest the best storage location."""
        available = self.get_available_drives()
        
        if not available:
            return None
        
        # Prefer largest removable drive
        removable = [d for d in available if d.is_removable]
        if removable:
            best = max(removable, key=lambda d: d.free_gb)
            return best.mount_point
        
        # Otherwise largest internal non-root drive
        internal = [d for d in available if not d.is_removable]
        if internal:
            best = max(internal, key=lambda d: d.free_gb)
            return best.mount_point
        
        return None
    
    def format_drive_options(self) -> List[Dict]:
        """Format drives for display in UI."""
        drives = self.get_available_drives()
        
        options = []
        
        # Default location
        options.append({
            "id": "default",
            "name": "Default Location (/var/lib)",
            "description": "Store data on the system drive",
            "path": "/var/lib",
            "size": "System dependent",
            "type": "internal"
        })
        
        # Home directory
        options.append({
            "id": "home",
            "name": "Home Directory (~/.home-server)",
            "description": "Store data in your home folder",
            "path": "~/.home-server",
            "size": "System dependent",
            "type": "internal"
        })
        
        # Detected drives
        for i, drive in enumerate(drives):
            drive_type = "external" if drive.is_removable else "internal"
            options.append({
                "id": f"drive_{i}",
                "name": drive.display_name,
                "description": f"{drive.filesystem} - {drive.free_gb:.1f} GB free",
                "path": drive.mount_point or f"/mnt/{drive.label or 'storage'}",
                "size": f"{drive.size_gb:.1f} GB total",
                "type": drive_type,
                "device": drive.device,
                "free_gb": drive.free_gb
            })
        
        # Custom option
        options.append({
            "id": "custom",
            "name": "Custom Location",
            "description": "Specify your own storage path",
            "path": None,
            "size": "User specified",
            "type": "custom"
        })
        
        return options
    
    def _parse_size(self, size_str: str) -> float:
        """Parse size string to GB."""
        size_str = size_str.strip()
        if not size_str:
            return 0.0
        
        # Extract number and unit
        match = re.match(r'([\d.]+)\s*([KMGT]?)', size_str, re.IGNORECASE)
        if not match:
            return 0.0
        
        number = float(match.group(1))
        unit = match.group(2).upper()
        
        multipliers = {
            '': 1e-9,  # Assume bytes if no unit
            'K': 1e-6,
            'M': 1e-3,
            'G': 1.0,
            'T': 1000.0
        }
        
        return number * multipliers.get(unit, 1e-9)
    
    def _get_usage(self, device: str, mount_point: Optional[str]) -> tuple:
        """Get usage stats for a device."""
        if not mount_point:
            return 0.0, 0.0
        
        try:
            result = subprocess.run(
                ["df", "-B1", mount_point],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    used = int(parts[2]) / (1024**3)  # Convert to GB
                    free = int(parts[3]) / (1024**3)
                    return used, free
        except Exception:
            pass
        
        return 0.0, 0.0
    
    def _is_removable_device(self, device_name: str) -> bool:
        """Check if device is removable."""
        try:
            # Check /sys/block/ for removable attribute
            base_device = re.sub(r'\d+$', '', device_name)  # Remove partition number
            removable_path = f"/sys/block/{base_device}/removable"
            
            if os.path.exists(removable_path):
                with open(removable_path, 'r') as f:
                    return f.read().strip() == '1'
        except Exception:
            pass
        
        # Fallback: check if it's USB
        try:
            result = subprocess.run(
                ["udevadm", "info", "--query=property", f"/dev/{device_name}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return 'ID_BUS=usb' in result.stdout or 'ID_USB_DRIVER' in result.stdout
        except Exception:
            pass
        
        return False
    
    def _fallback_detection(self) -> List[StorageDevice]:
        """Fallback detection using basic methods."""
        devices = []
        
        try:
            # Check /proc/mounts for mounted filesystems
            with open('/proc/mounts', 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2 and parts[0].startswith('/dev/'):
                        device = parts[0]
                        mount_point = parts[1]
                        
                        # Skip root and system mounts
                        if mount_point in ['/', '/boot', '/boot/efi']:
                            continue
                        
                        used, free = self._get_usage(device, mount_point)
                        
                        devices.append(StorageDevice(
                            device=device,
                            mount_point=mount_point,
                            size_gb=used + free,
                            used_gb=used,
                            free_gb=free,
                            filesystem="unknown",
                            label=None,
                            is_removable=False,
                            is_mounted=True
                        ))
        except Exception:
            pass
        
        return devices


def detect_storage_options() -> List[Dict]:
    """Convenience function to get storage options."""
    detector = DriveDetector()
    return detector.format_drive_options()


def suggest_best_storage() -> Optional[str]:
    """Suggest the best storage location."""
    detector = DriveDetector()
    return detector.suggest_storage_location()


if __name__ == "__main__":
    # Test drive detection
    detector = DriveDetector()
    drives = detector.detect_drives()
    
    print("Detected Storage Devices:")
    print("-" * 60)
    for drive in drives:
        type_str = "External" if drive.is_removable else "Internal"
        mount_str = f"mounted at {drive.mount_point}" if drive.mount_point else "not mounted"
        print(f"{drive.device}: {drive.size_gb:.1f} GB ({type_str}, {mount_str})")
        if drive.mount_point:
            print(f"  Free: {drive.free_gb:.1f} GB, Used: {drive.used_gb:.1f} GB")
    
    print("\nStorage Options for UI:")
    print("-" * 60)
    for opt in detector.format_drive_options():
        print(f"{opt['name']}: {opt.get('size', 'N/A')} free")

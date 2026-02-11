"""
Configuration Validation Module
Validates user configuration files and requirements.
"""
import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConfigValidationResult:
    """Result of configuration validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    def __init__(self):
        self.is_valid = True
        self.errors = []
        self.warnings = []
    
    def add_error(self, message: str):
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        self.warnings.append(message)


class ConfigValidator:
    """Validates configuration files and requirements."""
    
    VALID_USE_CASES = {
        'file_storage', 'media_server', 'ad_blocking', 
        'vpn', 'photos', 'backup', 'ai_assistant'
    }
    
    VALID_MEDIA_TYPES = {'movies', 'tv', 'music', 'photos'}
    
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    def __init__(self):
        self.result = ConfigValidationResult()
    
    def validate_config(self, config: Dict) -> ConfigValidationResult:
        """Validate a configuration dictionary."""
        self.result = ConfigValidationResult()
        
        # Check required structure
        if not isinstance(config, dict):
            self.result.add_error("Configuration must be a JSON object")
            return self.result
        
        # Validate use_cases
        self._validate_use_cases(config.get('use_cases', []))
        
        # Validate media_types
        self._validate_media_types(config.get('media_types', []))
        
        # Validate component flags
        self._validate_component_flags(config)
        
        # Validate storage path
        self._validate_storage_path(config.get('storage_path'))
        
        # Validate email
        self._validate_email(config.get('admin_email'))
        
        # Validate auth keys format (basic)
        self._validate_auth_keys(config)
        
        # Cross-field validation
        self._validate_consistency(config)
        
        return self.result
    
    def _validate_use_cases(self, use_cases: List):
        """Validate use_cases field."""
        if not isinstance(use_cases, list):
            self.result.add_error("'use_cases' must be a list")
            return
        
        if not use_cases:
            self.result.add_warning("No use cases specified - is this intentional?")
        
        for case in use_cases:
            if case not in self.VALID_USE_CASES:
                self.result.add_warning(f"Unknown use case: '{case}'")
    
    def _validate_media_types(self, media_types: List):
        """Validate media_types field."""
        if not isinstance(media_types, list):
            self.result.add_error("'media_types' must be a list")
            return
        
        for media_type in media_types:
            if media_type not in self.VALID_MEDIA_TYPES:
                self.result.add_warning(f"Unknown media type: '{media_type}'")
    
    def _validate_component_flags(self, config: Dict):
        """Validate boolean component flags."""
        boolean_fields = [
            'want_tailscale', 'want_adguard', 'want_openclaw',
            'want_immich', 'want_jellyfin'
        ]
        
        for field in boolean_fields:
            if field in config and not isinstance(config[field], bool):
                self.result.add_error(f"'{field}' must be a boolean (true/false)")
    
    def _validate_storage_path(self, path: Optional[str]):
        """Validate storage path with stricter checks."""
        if path is None:
            return
        
        if not isinstance(path, str):
            self.result.add_error("'storage_path' must be a string")
            return
        
        # Check for invalid characters
        invalid_chars = ['\\', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in path:
                self.result.add_error(f"'storage_path' contains invalid character: '{char}'")
                return
        
        # Check for shell metacharacters (security)
        shell_metachars = [';', '|', '&', '$', '(', ')', '`', '{', '}']
        for char in shell_metachars:
            if char in path:
                self.result.add_error(f"'storage_path' contains shell metacharacter: '{char}'")
                return
        
        # Check for relative paths (should be absolute or use ~)
        if not path.startswith('/') and not path.startswith('~'):
            self.result.add_warning(f"'storage_path' '{path}' should be absolute (start with / or ~)")
        
        # Check for parent directory traversal (security)
        if '..' in path:
            self.result.add_error("'storage_path' contains parent directory reference (..)")
        
        # Check for null bytes (security)
        if '\x00' in path:
            self.result.add_error("'storage_path' contains null bytes")
    
    def _validate_email(self, email: Optional[str]):
        """Validate admin email."""
        if email is None:
            return
        
        if not isinstance(email, str):
            self.result.add_error("'admin_email' must be a string")
            return
        
        if not self.EMAIL_REGEX.match(email):
            self.result.add_warning(f"'admin_email' '{email}' doesn't look like a valid email")
    
    def _validate_auth_keys(self, config: Dict):
        """Validate authentication keys format."""
        tailscale_key = config.get('tailscale_auth_key')
        if tailscale_key and isinstance(tailscale_key, str):
            if not tailscale_key.startswith('tskey-'):
                self.result.add_warning(
                    "Tailscale auth key should start with 'tskey-'"
                )
        
        openclaw_key = config.get('openclaw_gateway_token')
        if openclaw_key and isinstance(openclaw_key, str):
            if not openclaw_key.startswith('ocgw-'):
                self.result.add_warning(
                    "OpenClaw gateway token should start with 'ocgw-'"
                )
    
    def _validate_consistency(self, config: Dict):
        """Validate cross-field consistency."""
        use_cases = set(config.get('use_cases', []))
        
        # Check that media servers are selected if media_server is in use_cases
        if 'media_server' in use_cases:
            if not config.get('want_jellyfin') and not config.get('want_immich'):
                self.result.add_warning(
                    "'media_server' in use_cases but no media server selected (want_jellyfin/want_immich)"
                )
        
        # Check that VPN is selected if vpn is in use_cases
        if 'vpn' in use_cases and not config.get('want_tailscale'):
            self.result.add_warning(
                "'vpn' in use_cases but want_tailscale is false"
            )
        
        # Check that ad blocking is selected if ad_blocking is in use_cases
        if 'ad_blocking' in use_cases and not config.get('want_adguard'):
            self.result.add_warning(
                "'ad_blocking' in use_cases but want_adguard is false"
            )
        
        # Check that AI assistant is selected if ai_assistant is in use_cases
        if 'ai_assistant' in use_cases and not config.get('want_openclaw'):
            self.result.add_warning(
                "'ai_assistant' in use_cases but want_openclaw is false"
            )


def validate_config_file(config_path: str) -> Tuple[bool, List[str], List[str]]:
    """
    Validate a configuration file.
    
    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    path = Path(config_path)
    
    if not path.exists():
        return False, [f"Configuration file not found: {config_path}"], []
    
    if not path.is_file():
        return False, [f"Configuration path is not a file: {config_path}"], []
    
    try:
        # Check file size (prevent loading huge files)
        file_size = path.stat().st_size
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            return False, [f"Configuration file too large: {file_size} bytes (max 10MB)"], []
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError as e:
        return False, [f"Configuration file is not valid UTF-8: {e}"], []
    except IOError as e:
        return False, [f"Cannot read {config_path}: {e}"], []
    
    try:
        config = json.loads(content)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON in {config_path}: {e}"], []
    
    validator = ConfigValidator()
    result = validator.validate_config(config)
    
    return result.is_valid, result.errors, result.warnings


def validate_requirements(requirements: Dict) -> Tuple[bool, List[str], List[str]]:
    """Validate user requirements dictionary."""
    validator = ConfigValidator()
    result = validator.validate_config(requirements)
    return result.is_valid, result.errors, result.warnings


if __name__ == "__main__":
    # Test validation
    test_config = {
        "use_cases": ["media_server", "vpn"],
        "media_types": ["movies", "photos"],
        "want_tailscale": True,
        "want_adguard": False,
        "want_openclaw": False,
        "want_immich": True,
        "want_jellyfin": True,
        "storage_path": "~/media",
        "admin_email": "admin@example.com"
    }
    
    validator = ConfigValidator()
    result = validator.validate_config(test_config)
    
    print(f"Valid: {result.is_valid}")
    if result.errors:
        print("Errors:")
        for e in result.errors:
            print(f"  - {e}")
    if result.warnings:
        print("Warnings:")
        for w in result.warnings:
            print(f"  - {w}")

"""
Security Utilities Module
Centralized security functions for input validation, sanitization, and secure operations.
"""
import re
import shlex
import hashlib
import secrets
import hmac
from pathlib import Path
from typing import Optional, Tuple, List


class SecurityError(Exception):
    """Security-related error."""
    pass


class InputValidator:
    """Validates and sanitizes user inputs."""
    
    # Whitelist patterns for safe strings
    SAFE_PATH_PATTERN = re.compile(r'^[a-zA-Z0-9_/.~\-]+$')
    SAFE_DOMAIN_PATTERN = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*'
        r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])$'
    )
    SAFE_EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    SAFE_LABEL_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\s]+$')
    
    # Dangerous shell metacharacters
    DANGEROUS_CHARS = set(';|&$`\\<>!\n\r')
    
    @classmethod
    def validate_storage_path(cls, path: str) -> Tuple[bool, str]:
        """
        Validate storage path is safe.
        Returns (is_valid, error_message)
        """
        if not path or not isinstance(path, str):
            return False, "Path cannot be empty"
        
        # Check length
        if len(path) > 4096:
            return False, "Path too long (max 4096 characters)"
        
        # Check for null bytes
        if '\x00' in path:
            return False, "Path contains null bytes"
        
        # Check for dangerous characters
        if any(c in path for c in cls.DANGEROUS_CHARS):
            return False, f"Path contains dangerous characters: {cls.DANGEROUS_CHARS}"
        
        # Check for parent directory traversal
        if '..' in path:
            return False, "Path cannot contain parent directory references (..)"
        
        # Expand and normalize
        expanded = Path(path).expanduser().resolve()
        
        # Check against whitelist pattern (for the original string)
        # Allow common safe paths like /mnt/storage, /home/user/data, etc.
        test_path = path.replace('~', '').replace('/', '').replace('-', '').replace('_', '').replace('.', '')
        if test_path and not test_path.isalnum():
            return False, "Path contains invalid characters"
        
        return True, str(expanded)
    
    @classmethod
    def sanitize_for_shell(cls, value: str) -> str:
        """
        Sanitize a value for safe use in shell commands.
        Uses shlex.quote for proper escaping.
        """
        if not isinstance(value, str):
            value = str(value)
        return shlex.quote(value)
    
    @classmethod
    def validate_domain(cls, domain: str) -> Tuple[bool, str]:
        """
        Validate domain name format.
        Returns (is_valid, error_message)
        """
        if not domain or not isinstance(domain, str):
            return False, "Domain cannot be empty"
        
        # Remove protocol if present (common mistake)
        domain = domain.lower().strip()
        if domain.startswith(('http://', 'https://')):
            domain = domain.split('://', 1)[1]
        
        # Remove path if present
        domain = domain.split('/')[0]
        
        # Check length
        if len(domain) > 253:
            return False, "Domain too long (max 253 characters)"
        
        # Check for dangerous characters
        if any(c in domain for c in cls.DANGEROUS_CHARS):
            return False, "Domain contains invalid characters"
        
        # Validate format
        if not cls.SAFE_DOMAIN_PATTERN.match(domain):
            return False, "Invalid domain format"
        
        return True, domain
    
    @classmethod
    def validate_email(cls, email: str) -> Tuple[bool, str]:
        """Validate email format."""
        if not email or not isinstance(email, str):
            return False, "Email cannot be empty"
        
        if len(email) > 254:
            return False, "Email too long"
        
        if not cls.SAFE_EMAIL_PATTERN.match(email):
            return False, "Invalid email format"
        
        return True, email.lower().strip()
    
    @classmethod
    def validate_label(cls, label: str) -> Tuple[bool, str]:
        """Validate a label/name is safe."""
        if not label or not isinstance(label, str):
            return False, "Label cannot be empty"
        
        if len(label) > 100:
            return False, "Label too long (max 100 characters)"
        
        if not cls.SAFE_LABEL_PATTERN.match(label):
            return False, "Label contains invalid characters"
        
        return True, label.strip()
    
    @classmethod
    def validate_api_key(cls, key: str, provider: str) -> Tuple[bool, str]:
        """
        Validate API key format (basic sanity checks).
        Doesn't validate against service, just format.
        """
        if not key or not isinstance(key, str):
            return False, "API key cannot be empty"
        
        # Minimum length
        if len(key) < 10:
            return False, "API key too short"
        
        # Maximum length
        if len(key) > 500:
            return False, "API key too long"
        
        # Check for newlines
        if '\n' in key or '\r' in key:
            return False, "API key contains newlines"
        
        # Provider-specific checks
        if provider == 'openai' and not key.startswith('sk-'):
            return False, "OpenAI keys should start with 'sk-'"
        
        if provider == 'anthropic' and not key.startswith('sk-ant-'):
            return False, "Anthropic keys should start with 'sk-ant-'"
        
        if provider == 'tailscale' and not key.startswith('tskey-'):
            return False, "Tailscale keys should start with 'tskey-'"
        
        return True, key.strip()


class CommandBuilder:
    """Builds shell commands safely without injection vulnerabilities."""
    
    @staticmethod
    def build_mkdir(path: str) -> List[str]:
        """Build safe mkdir command."""
        is_valid, sanitized_path = InputValidator.validate_storage_path(path)
        if not is_valid:
            raise SecurityError(f"Invalid path: {sanitized_path}")
        return ['mkdir', '-p', sanitized_path]
    
    @staticmethod
    def build_docker_run(
        image: str,
        name: str,
        ports: List[Tuple[int, int]] = None,
        volumes: List[Tuple[str, str, str]] = None,
        env_vars: List[Tuple[str, str]] = None,
        network: str = None,
        cap_drop: bool = True,
        read_only: bool = False,
        memory_limit: str = None,
        cpu_limit: str = None
    ) -> List[str]:
        """
        Build safe docker run command.
        
        Args:
            image: Docker image (should be pinned to digest)
            name: Container name
            ports: List of (host_port, container_port)
            volumes: List of (host_path, container_path, mode) where mode is 'ro' or 'rw'
            env_vars: List of (key, value)
            network: Network name
            cap_drop: Drop all capabilities
            read_only: Make filesystem read-only
            memory_limit: Memory limit (e.g., '2g')
            cpu_limit: CPU limit (e.g., '2.0')
        """
        cmd = ['docker', 'run', '-d', '--restart', 'unless-stopped']
        
        # Security hardening
        if cap_drop:
            cmd.extend(['--cap-drop', 'ALL'])
            cmd.extend(['--cap-add', 'CHOWN'])
            cmd.extend(['--cap-add', 'SETGID'])
            cmd.extend(['--cap-add', 'SETUID'])
            cmd.extend(['--security-opt', 'no-new-privileges:true'])
        
        if read_only:
            cmd.append('--read-only')
            cmd.extend(['--tmpfs', '/tmp:noexec,nosuid,size=100m'])
        
        # Resource limits
        if memory_limit:
            cmd.extend(['--memory', memory_limit])
            cmd.extend(['--memory-swap', memory_limit])
        
        if cpu_limit:
            cmd.extend(['--cpus', cpu_limit])
        
        # Name
        cmd.extend(['--name', name])
        
        # Network
        if network:
            cmd.extend(['--network', network])
        
        # Ports
        if ports:
            for host_port, container_port in ports:
                if not (1 <= host_port <= 65535 and 1 <= container_port <= 65535):
                    raise SecurityError(f"Invalid port numbers: {host_port}, {container_port}")
                cmd.extend(['-p', f'{host_port}:{container_port}'])
        
        # Volumes
        if volumes:
            for host_path, container_path, mode in volumes:
                is_valid, sanitized_path = InputValidator.validate_storage_path(host_path)
                if not is_valid:
                    raise SecurityError(f"Invalid volume path: {sanitized_path}")
                if mode not in ['ro', 'rw']:
                    mode = 'rw'
                cmd.extend(['-v', f'{sanitized_path}:{container_path}:{mode}'])
        
        # Environment variables
        if env_vars:
            for key, value in env_vars:
                # Validate env var name
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                    raise SecurityError(f"Invalid environment variable name: {key}")
                cmd.extend(['-e', f'{key}={value}'])
        
        # Image (should be pinned)
        cmd.append(image)
        
        return cmd
    
    @staticmethod
    def build_certbot(domain: str, email: str, method: str = 'nginx') -> List[str]:
        """Build safe certbot command."""
        is_valid, sanitized_domain = InputValidator.validate_domain(domain)
        if not is_valid:
            raise SecurityError(f"Invalid domain: {sanitized_domain}")
        
        is_valid, sanitized_email = InputValidator.validate_email(email)
        if not is_valid:
            raise SecurityError(f"Invalid email: {sanitized_email}")
        
        if method not in ['nginx', 'apache', 'standalone', 'dns']:
            raise SecurityError(f"Invalid certbot method: {method}")
        
        return [
            'certbot',
            f'--{method}',
            '-d', sanitized_domain,
            '--agree-tos',
            '--non-interactive',
            '--email', sanitized_email
        ]


class CredentialManager:
    """Manages secure storage of credentials."""
    
    @staticmethod
    def mask_in_log(value: str, visible_chars: int = 4) -> str:
        """
        Mask a sensitive value for logging.
        Shows only first N characters, rest is ***
        """
        if not value or len(value) <= visible_chars:
            return '***'
        return value[:visible_chars] + '***'
    
    @staticmethod
    def sanitize_command_for_logging(command: str) -> str:
        """
        Remove sensitive data from command before logging.
        """
        import re
        
        patterns = [
            # API keys
            (re.compile(r'(sk-[a-zA-Z0-9]{20,})'), r'***MASKED***'),
            (re.compile(r'(sk-ant-[a-zA-Z0-9]{20,})'), r'***MASKED***'),
            (re.compile(r'(tskey-[a-zA-Z0-9-]+)'), r'***MASKED***'),
            # Auth tokens in various formats
            (re.compile(r'(authkey=)([^\s&]+)'), r'\1***MASKED***'),
            (re.compile(r'(api[_-]?key[=:])[^\s&]+', re.I), r'\1***MASKED***'),
            (re.compile(r'(password[=:])[^\s&]+', re.I), r'\1***MASKED***'),
            (re.compile(r'(token[=:])[^\s&]+', re.I), r'\1***MASKED***'),
            # HTTP headers
            (re.compile(r'(Authorization:\s*Bearer\s+)[^\s]+', re.I), r'\1***MASKED***'),
            (re.compile(r'(X-API-Key:\s*)[^\s]+', re.I), r'\1***MASKED***'),
        ]
        
        sanitized = command
        for pattern, replacement in patterns:
            sanitized = pattern.sub(replacement, sanitized)
        
        return sanitized


class CSRFProtection:
    """CSRF token generation and validation."""
    
    TOKEN_LENGTH = 32
    
    @classmethod
    def generate_token(cls) -> str:
        """Generate a secure CSRF token."""
        return secrets.token_urlsafe(cls.TOKEN_LENGTH)
    
    @classmethod
    def validate_token(cls, token: str, expected_token: str) -> bool:
        """
        Validate CSRF token using constant-time comparison.
        """
        if not token or not expected_token:
            return False
        
        if len(token) != len(expected_token):
            return False
        
        return hmac.compare_digest(token, expected_token)


# Convenience functions for common validations
def validate_storage_path(path: str) -> str:
    """Validate and return sanitized storage path."""
    is_valid, result = InputValidator.validate_storage_path(path)
    if not is_valid:
        raise SecurityError(result)
    return result


def validate_domain(domain: str) -> str:
    """Validate and return sanitized domain."""
    is_valid, result = InputValidator.validate_domain(domain)
    if not is_valid:
        raise SecurityError(result)
    return result


def sanitize_shell(value: str) -> str:
    """Sanitize value for shell use."""
    return InputValidator.sanitize_for_shell(value)


def mask_sensitive(value: str) -> str:
    """Mask sensitive value for logging."""
    return CredentialManager.mask_in_log(value)

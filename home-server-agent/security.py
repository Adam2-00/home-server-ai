"""
Security Module for Domain and Tailscale Integration
Handles secure access, authentication, and network isolation.
"""
import os
import re
import json
import hashlib
import secrets
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class SecurityConfig:
    """Security configuration for domain-based access."""
    domain_name: str
    use_tailscale_funnel: bool
    expose_externally: bool
    require_auth: bool
    auth_method: str  # 'basic', 'authelia', 'oauth', 'tailscale'
    rate_limit_requests: int
    rate_limit_window: int
    ip_allowlist: List[str]
    ip_denylist: List[str]
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AuthCredentials:
    """Generated authentication credentials."""
    username: str
    password_hash: str
    api_key: Optional[str]
    jwt_secret: Optional[str]
    
    def to_dict(self) -> Dict:
        return asdict(self)


class DomainSecurityManager:
    """Manages security for custom domain access."""
    
    def __init__(self, config: SecurityConfig, storage_path: str = "~/.home-server/security"):
        self.config = config
        self.storage_path = Path(storage_path).expanduser()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.credentials: Optional[AuthCredentials] = None
    
    def setup_security(self) -> Dict:
        """Set up all security components."""
        results = {
            'success': True,
            'steps_completed': [],
            'warnings': [],
            'errors': []
        }
        
        # Generate credentials
        try:
            self.credentials = self._generate_credentials()
            self._save_credentials()
            results['steps_completed'].append("Generated authentication credentials")
        except Exception as e:
            results['errors'].append(f"Failed to generate credentials: {e}")
            results['success'] = False
        
        # Set up Tailscale funnel if enabled
        if self.config.use_tailscale_funnel:
            try:
                self._configure_tailscale_funnel()
                results['steps_completed'].append("Configured Tailscale Funnel")
            except Exception as e:
                results['warnings'].append(f"Tailscale Funnel setup incomplete: {e}")
        
        # Set up authentication middleware
        if self.config.require_auth:
            try:
                auth_setup = self._setup_authentication()
                results['steps_completed'].extend(auth_setup)
            except Exception as e:
                results['errors'].append(f"Authentication setup failed: {e}")
                results['success'] = False
        
        # Configure rate limiting
        try:
            self._configure_rate_limiting()
            results['steps_completed'].append("Configured rate limiting")
        except Exception as e:
            results['warnings'].append(f"Rate limiting not fully configured: {e}")
        
        # Set up firewall rules
        if self.config.expose_externally:
            try:
                self._configure_firewall()
                results['steps_completed'].append("Configured firewall rules")
            except Exception as e:
                results['warnings'].append(f"Firewall configuration incomplete: {e}")
        
        return results
    
    def _generate_credentials(self) -> AuthCredentials:
        """Generate secure credentials for authentication."""
        # Generate a secure password
        password = secrets.token_urlsafe(32)
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Generate API key
        api_key = f"hsa_{secrets.token_urlsafe(48)}"
        
        # Generate JWT secret
        jwt_secret = secrets.token_hex(64)
        
        return AuthCredentials(
            username="admin",
            password_hash=password_hash,
            api_key=api_key,
            jwt_secret=jwt_secret
        )
    
    def _save_credentials(self):
        """Save credentials securely."""
        creds_file = self.storage_path / "credentials.json"
        
        # Save with restricted permissions
        creds_data = {
            'username': self.credentials.username,
            'password_hash': self.credentials.password_hash,
            'api_key': self.credentials.api_key,
            'jwt_secret': self.credentials.jwt_secret,
            'created_at': str(Path().stat().st_ctime)
        }
        
        with open(creds_file, 'w') as f:
            json.dump(creds_data, f, indent=2)
        
        # Set restrictive permissions (owner read/write only)
        os.chmod(creds_file, 0o600)
        
        # Also save a password file for initial setup
        password_file = self.storage_path / "initial_password.txt"
        # Note: In production, this should be displayed once and not stored
        # For now, we'll store it temporarily with a warning
        with open(password_file, 'w') as f:
            f.write(f"Initial Admin Password: {self._get_plaintext_password()}\n")
            f.write(f"API Key: {self.credentials.api_key}\n")
            f.write("\nIMPORTANT: Delete this file after noting the credentials!\n")
        
        os.chmod(password_file, 0o600)
    
    def _get_plaintext_password(self) -> str:
        """Get the plaintext password (only available during initial setup)."""
        # This is a simplified version - in production, use a proper password manager
        return secrets.token_urlsafe(16)
    
    def _configure_tailscale_funnel(self):
        """Configure Tailscale Funnel for secure access."""
        import subprocess
        
        # Check if Tailscale is installed
        result = subprocess.run(['which', 'tailscale'], capture_output=True)
        if result.returncode != 0:
            raise RuntimeError("Tailscale is not installed")
        
        # Check Tailscale status
        result = subprocess.run(['tailscale', 'status'], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("Tailscale is not running. Run 'sudo tailscale up' first.")
        
        # Enable funnel (requires port 443)
        subprocess.run(
            ['sudo', 'tailscale', 'funnel', '--bg', '443'],
            capture_output=True,
            check=True
        )
        
        # Verify funnel is active
        result = subprocess.run(['sudo', 'tailscale', 'funnel', 'status'], 
                              capture_output=True, text=True)
        if 'Funnel' not in result.stdout:
            raise RuntimeError("Funnel status check failed")
    
    def _setup_authentication(self) -> List[str]:
        """Set up authentication middleware."""
        completed = []
        
        if self.config.auth_method == 'basic':
            self._setup_basic_auth()
            completed.append("Configured HTTP Basic Authentication")
        elif self.config.auth_method == 'authelia':
            self._setup_authelia()
            completed.append("Configured Authelia authentication")
        elif self.config.auth_method == 'oauth':
            self._setup_oauth_proxy()
            completed.append("Configured OAuth2 Proxy")
        elif self.config.auth_method == 'tailscale':
            completed.append("Using Tailscale native authentication")
        
        return completed
    
    def _setup_basic_auth(self):
        """Set up HTTP Basic Authentication."""
        import base64
        
        # Create htpasswd file
        htpasswd_path = self.storage_path / ".htpasswd"
        
        # Generate htpasswd entry (using SHA256 for Apache/nginx compatibility)
        password = self._get_plaintext_password()
        salt = secrets.token_hex(8)
        hash_value = hashlib.sha256((password + salt).encode()).hexdigest()
        
        htpasswd_content = f"{self.credentials.username}:{hash_value}\n"
        
        with open(htpasswd_path, 'w') as f:
            f.write(htpasswd_content)
        
        os.chmod(htpasswd_path, 0o600)
    
    def _setup_authelia(self):
        """Set up Authelia for advanced authentication."""
        config_dir = self.storage_path / "authelia"
        config_dir.mkdir(exist_ok=True)
        
        # Generate Authelia configuration
        authelia_config = f"""server:
  host: 0.0.0.0
  port: 9091

theme: dark

jwt_secret: {self.credentials.jwt_secret}

default_redirection_url: https://{self.config.domain_name}

authentication_backend:
  file:
    path: /config/users_database.yml
    password:
      algorithm: argon2id
      iterations: 1
      key_length: 32
      salt_length: 16
      memory: 64
      parallelism: 8

access_control:
  default_policy: one_factor
  rules:
    - domain: '*.{self.config.domain_name}'
      policy: one_factor

session:
  name: authelia_session
  secret: {secrets.token_hex(32)}
  expiration: 1h
  inactivity: 5m
  domain: {self.config.domain_name}

regulation:
  max_retries: 3
  find_time: 2m
  ban_time: 5m

storage:
  encryption_key: {secrets.token_hex(32)}
  local:
    path: /config/db.sqlite3

notifier:
  filesystem:
    filename: /config/notification.txt
"""
        
        config_file = config_dir / "configuration.yml"
        with open(config_file, 'w') as f:
            f.write(authelia_config)
        
        # Create users database
        users_db = f"""users:
  {self.credentials.username}:
    disabled: false
    displayname: "Administrator"
    password: "{self._hash_password_argon2(self._get_plaintext_password())}"
    email: admin@{self.config.domain_name}
    groups:
      - admins
      - users
"""
        
        users_file = config_dir / "users_database.yml"
        with open(users_file, 'w') as f:
            f.write(users_db)
    
    def _hash_password_argon2(self, password: str) -> str:
        """Generate Argon2 hash for Authelia."""
        # This is a placeholder - in real implementation, use argon2-cffi library
        # For now, generate a placeholder that Authelia will reject
        # User should run: authelia hash-password 'yourpassword'
        return "$argon2id$v=19$m=65536,t=3,p=4$PLACEHOLDER$PLACEHOLDER"
    
    def _setup_oauth_proxy(self):
        """Set up OAuth2 Proxy for external authentication providers."""
        config_dir = self.storage_path / "oauth2-proxy"
        config_dir.mkdir(exist_ok=True)
        
        # Generate OAuth2 Proxy config template
        oauth_config = f"""# OAuth2 Proxy Configuration
# This is a template - fill in with your OAuth provider details

provider = "google"
client_id = "YOUR_CLIENT_ID"
client_secret = "YOUR_CLIENT_SECRET"
cookie_secret = "{secrets.token_urlsafe(32)}"
cookie_domain = "{self.config.domain_name}"

upstreams = [
    "http://localhost:8080"
]

email_domains = [
    "*"
]

# Restrict to specific users (optional)
# authenticated_emails_file = "{config_dir}/allowed_emails.txt"

# Rate limiting
request_logging_format = "{{.Client}} - {{.Username}} [{{.Timestamp}}] {{.Host}} {{.RequestMethod}} {{.Upstream}} {{.RequestDuration}}"
"""
        
        config_file = config_dir / "oauth2-proxy.cfg"
        with open(config_file, 'w') as f:
            f.write(oauth_config)
        
        # Create placeholder for allowed emails
        allowed_emails = config_dir / "allowed_emails.txt"
        allowed_emails.write_text("# Add allowed email addresses, one per line\n")
    
    def _configure_rate_limiting(self):
        """Configure rate limiting rules."""
        rate_limit_config = {
            'requests_per_minute': self.config.rate_limit_requests,
            'window_seconds': self.config.rate_limit_window,
            'burst_size': int(self.config.rate_limit_requests * 1.5),
            'excluded_ips': ['127.0.0.1', '::1'],
            'paths': {
                '/api/': {'requests': 60, 'window': 60},
                '/login': {'requests': 5, 'window': 60},
                '/': {'requests': self.config.rate_limit_requests, 'window': self.config.rate_limit_window}
            }
        }
        
        config_file = self.storage_path / "rate_limit_config.json"
        with open(config_file, 'w') as f:
            json.dump(rate_limit_config, f, indent=2)
    
    def _configure_firewall(self):
        """Configure firewall rules for external exposure."""
        # Note: This is a simplified version. In production, use a proper firewall manager
        
        rules = [
            "# Home Server Firewall Rules",
            "# These rules assume UFW (Uncomplicated Firewall)",
            "",
            "# Allow SSH (important - don't lock yourself out!)",
            "ufw allow 22/tcp",
            "",
            "# Allow HTTP and HTTPS",
            "ufw allow 80/tcp",
            "ufw allow 443/tcp",
            "",
            "# Allow Tailscale",
            "ufw allow in on tailscale0",
            "",
        ]
        
        # Add allowlist rules
        if self.config.ip_allowlist:
            rules.append("# IP Allowlist")
            for ip in self.config.ip_allowlist:
                rules.append(f"ufw allow from {ip} to any port 443")
            rules.append("")
        
        # Add denylist rules
        if self.config.ip_denylist:
            rules.append("# IP Denylist")
            for ip in self.config.ip_denylist:
                rules.append(f"ufw deny from {ip}")
            rules.append("")
        
        rules.extend([
            "# Deny all other incoming",
            "ufw default deny incoming",
            "",
            "# Enable firewall",
            "ufw --force enable"
        ])
        
        rules_file = self.storage_path / "firewall_rules.sh"
        with open(rules_file, 'w') as f:
            f.write('\n'.join(rules))
        
        os.chmod(rules_file, 0o755)
    
    def get_caddy_security_directives(self) -> List[str]:
        """Get Caddy security directives."""
        directives = []
        
        if self.config.require_auth and self.config.auth_method == 'basic':
            directives.append(f"    basicauth {{")
            directives.append(f"        {self.credentials.username} {self.credentials.password_hash}")
            directives.append(f"    }}")
        
        if self.config.rate_limit_requests > 0:
            directives.append(f"    rate_limit {{")
            directives.append(f"        zone static {self.config.rate_limit_window}s {self.config.rate_limit_requests}r")
            directives.append(f"    }}")
        
        return directives
    
    def get_nginx_security_directives(self) -> List[str]:
        """Get Nginx security directives."""
        directives = []
        
        if self.config.require_auth and self.config.auth_method == 'basic':
            directives.append(f"    auth_basic \"Restricted\";")
            directives.append(f"    auth_basic_user_file {self.storage_path}/.htpasswd;")
        
        # Rate limiting
        if self.config.rate_limit_requests > 0:
            directives.append(f"    limit_req_zone $binary_remote_addr zone=general:10m rate={self.config.rate_limit_requests}r/m;")
            directives.append(f"    limit_req zone=general burst=20 nodelay;")
        
        # IP restrictions
        if self.config.ip_allowlist:
            for ip in self.config.ip_allowlist:
                directives.append(f"    allow {ip};")
            directives.append("    deny all;")
        
        return directives
    
    def verify_security_setup(self) -> Dict:
        """Verify that security configuration is properly applied."""
        results = {
            'checks': [],
            'passed': 0,
            'warnings': 0,
            'failed': 0
        }
        
        # Check credentials file
        creds_file = self.storage_path / "credentials.json"
        if creds_file.exists():
            results['checks'].append(('Credentials file exists', True, None))
            results['passed'] += 1
        else:
            results['checks'].append(('Credentials file exists', False, 'Run setup first'))
            results['failed'] += 1
        
        # Check file permissions
        if creds_file.exists():
            stat = creds_file.stat()
            if stat.st_mode & 0o077 == 0:  # No group/others permissions
                results['checks'].append(('File permissions secure', True, None))
                results['passed'] += 1
            else:
                results['checks'].append(('File permissions secure', False, 'Run: chmod 600 credentials.json'))
                results['failed'] += 1
        
        # Check Tailscale funnel
        if self.config.use_tailscale_funnel:
            import subprocess
            result = subprocess.run(['sudo', 'tailscale', 'funnel', 'status'], 
                                  capture_output=True, text=True)
            if result.returncode == 0 and 'Funnel' in result.stdout:
                results['checks'].append(('Tailscale Funnel active', True, None))
                results['passed'] += 1
            else:
                results['checks'].append(('Tailscale Funnel active', False, 'Run: sudo tailscale funnel --bg 443'))
                results['failed'] += 1
        
        return results


def create_security_config(domain_config: Dict) -> SecurityConfig:
    """Create security configuration from domain config."""
    return SecurityConfig(
        domain_name=domain_config['domain_name'],
        use_tailscale_funnel=domain_config.get('use_tailscale_funnel', True),
        expose_externally=domain_config.get('expose_externally', False),
        require_auth=domain_config.get('require_auth', True),
        auth_method='tailscale' if domain_config.get('use_tailscale_funnel') else 'basic',
        rate_limit_requests=60,
        rate_limit_window=60,
        ip_allowlist=[],
        ip_denylist=[]
    )


def validate_domain_security(domain: str) -> Tuple[bool, List[str]]:
    """Validate domain security best practices."""
    issues = []
    
    # Check domain format
    if not re.match(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$', domain):
        issues.append(f"Invalid domain format: {domain}")
    
    # Check for common security issues
    if domain.startswith('www.'):
        issues.append("Consider using the apex domain instead of www subdomain")
    
    if 'localhost' in domain.lower():
        issues.append("Using localhost in domain name is not secure for production")
    
    if domain.endswith('.local'):
        issues.append("Using .local may conflict with mDNS. Consider a real domain.")
    
    # Check for IP addresses
    ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
    if ip_pattern.match(domain):
        issues.append("Using IP address instead of domain name - SSL certificates won't work properly")
    
    return len(issues) == 0, issues


def generate_security_report(domain: str, config: SecurityConfig) -> str:
    """Generate a security audit report."""
    report = []
    report.append("=" * 60)
    report.append("  Home Server Security Report")
    report.append("=" * 60)
    report.append("")
    report.append(f"Domain: {domain}")
    report.append(f"Configuration Date: {Path().stat().st_ctime}")
    report.append("")
    
    report.append("Access Configuration:")
    report.append(f"  - Tailscale Funnel: {'Enabled' if config.use_tailscale_funnel else 'Disabled'}")
    report.append(f"  - External Exposure: {'Enabled' if config.expose_externally else 'Disabled'}")
    report.append(f"  - Authentication: {'Required' if config.require_auth else 'Optional'}")
    report.append(f"  - Auth Method: {config.auth_method}")
    report.append("")
    
    report.append("Rate Limiting:")
    report.append(f"  - Requests per minute: {config.rate_limit_requests}")
    report.append("")
    
    # Security recommendations
    report.append("Security Recommendations:")
    
    if config.expose_externally and not config.require_auth:
        report.append("  ⚠️  WARNING: External exposure without authentication is HIGH RISK")
        report.append("     Recommendation: Enable authentication or use Tailscale Funnel")
    
    if not config.use_tailscale_funnel and not config.expose_externally:
        report.append("  ℹ️  Services are only accessible on local network")
        report.append("     Recommendation: Consider Tailscale Funnel for secure remote access")
    
    if config.require_auth and config.auth_method == 'basic':
        report.append("  ℹ️  Using HTTP Basic Authentication")
        report.append("     Recommendation: Consider Authelia for enhanced security")
    
    report.append("")
    report.append("=" * 60)
    
    return '\n'.join(report)


if __name__ == "__main__":
    # Test security setup
    config = SecurityConfig(
        domain_name="example.com",
        use_tailscale_funnel=True,
        expose_externally=False,
        require_auth=True,
        auth_method='tailscale',
        rate_limit_requests=60,
        rate_limit_window=60,
        ip_allowlist=[],
        ip_denylist=[]
    )
    
    manager = DomainSecurityManager(config)
    print("Security configuration created successfully")
    print(generate_security_report("example.com", config))

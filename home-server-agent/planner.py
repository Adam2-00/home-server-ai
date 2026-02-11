"""
Planning Engine - GPT-4 Integration
Generates installation plans based on hardware and requirements.
"""
import json
import os
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

try:
    from openai import OpenAI, APIError, APITimeoutError
except ImportError:
    OpenAI = None
    APIError = None
    APITimeoutError = None

from retry_utils import retry_with_backoff

# Setup module logger
logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """Single step in the installation plan."""
    step_number: int
    name: str
    description: str
    command: Optional[str]
    commands: List[str]  # For multi-command steps
    requires_sudo: bool
    check_command: Optional[str]  # Command to verify step succeeded
    rollback_command: Optional[str]
    expected_output: Optional[str]
    error_hint: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class InstallationPlan:
    """Full installation plan."""
    title: str
    description: str
    prerequisites: List[str]
    steps: List[PlanStep]
    estimated_time_minutes: int
    known_issues: List[str]
    post_install_notes: List[str]
    
    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'description': self.description,
            'prerequisites': self.prerequisites,
            'steps': [s.to_dict() for s in self.steps],
            'estimated_time_minutes': self.estimated_time_minutes,
            'known_issues': self.known_issues,
            'post_install_notes': self.post_install_notes
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class PlanningEngine:
    """Generates installation plans using configurable AI provider."""
    
    SYSTEM_PROMPT = """You are a Linux system administration expert. Your task is to create detailed, step-by-step installation plans for home server software.

Rules:
1. Commands must be safe and follow best practices
2. Use apt for package management on Debian/Ubuntu
3. Prefer Docker/Compose for services when appropriate
4. Include verification steps after each installation
5. Consider the specific hardware profile provided
6. Handle common errors proactively

Output must be valid JSON with this structure:
{
  "title": "string",
  "description": "string", 
  "prerequisites": ["string"],
  "steps": [
    {
      "step_number": 1,
      "name": "string",
      "description": "string",
      "command": "string or null",
      "commands": ["string"],
      "requires_sudo": true/false,
      "check_command": "string or null",
      "rollback_command": "string or null",
      "expected_output": "string or null",
      "error_hint": "string"
    }
  ],
  "estimated_time_minutes": number,
  "known_issues": ["string"],
  "post_install_notes": ["string"]
}"""

    def __init__(self, api_key: Optional[str] = None, ai_config: Optional[Dict] = None):
        """
        Initialize planning engine.
        
        Args:
            api_key: Legacy OpenAI API key (for backward compatibility)
            ai_config: Full AI provider configuration dict with provider, model, api_key, base_url
        """
        from ai_provider import AIProviderConfig
        
        self.ai_config = None
        
        if ai_config:
            # Use provided config
            self.ai_config = AIProviderConfig(**ai_config)
        elif api_key:
            # Legacy: assume OpenAI
            self.ai_config = AIProviderConfig(
                provider='openai',
                model='gpt-4o-mini',
                api_key=api_key
            )
        else:
            # Try environment
            from ai_provider import get_ai_config_from_env
            self.ai_config = get_ai_config_from_env()
    
    def generate_plan(self, hardware_profile: Dict, user_requirements: Dict) -> InstallationPlan:
        """Generate installation plan using configured AI provider."""
        if not self.ai_config:
            print("   Using template plan (no AI provider configured)")
            logger.info("No AI provider configured, using template plan")
            return self._generate_template_plan(hardware_profile, user_requirements)
        
        # Validate inputs
        if not isinstance(hardware_profile, dict):
            raise ValueError(f"hardware_profile must be dict, got {type(hardware_profile).__name__}")
        if not isinstance(user_requirements, dict):
            raise ValueError(f"user_requirements must be dict, got {type(user_requirements).__name__}")
        
        prompt = self._build_prompt(hardware_profile, user_requirements)
        
        try:
            from ai_provider import call_ai_with_config
            plan_data = call_ai_with_config(
                self.ai_config,
                self.SYSTEM_PROMPT,
                prompt,
                expect_json=True
            )
            
            if plan_data:
                return self._parse_plan(plan_data)
            else:
                print("   AI call failed, using template plan")
                return self._generate_template_plan(hardware_profile, user_requirements)
            
        except json.JSONDecodeError as e:
            print(f"   Warning: AI returned invalid JSON ({e}), using template plan")
            logger.warning(f"AI JSON decode error: {e}")
            return self._generate_template_plan(hardware_profile, user_requirements)
        except ValueError as e:
            print(f"   Warning: AI plan validation failed ({e}), using template plan")
            logger.warning(f"AI plan validation error: {e}")
            return self._generate_template_plan(hardware_profile, user_requirements)
        except Exception as e:
            print(f"   Warning: AI plan generation failed ({e}), using template plan")
            logger.warning(f"AI plan generation error: {type(e).__name__}: {e}")
            return self._generate_template_plan(hardware_profile, user_requirements)
    def _build_prompt(self, hardware: Dict, requirements: Dict) -> str:
        components = []
        if requirements.get('want_tailscale'):
            components.append("Tailscale VPN")
        if requirements.get('want_adguard'):
            components.append("AdGuard Home")
        if requirements.get('want_openclaw'):
            components.append("OpenClaw")
        if requirements.get('want_immich'):
            components.append("Immich photo server")
        if requirements.get('want_jellyfin'):
            components.append("Jellyfin media server")
        
        return f"""Create an installation plan for a home server with these components: {', '.join(components)}

HARDWARE PROFILE:
```json
{json.dumps(hardware, indent=2)}
```

USER REQUIREMENTS:
```json
{json.dumps(requirements, indent=2)}
```

Generate a complete installation plan as JSON. Include:
1. Prerequisites check
2. Docker installation (if needed)
3. Each component installation with verification
4. Post-installation configuration steps

The target system is {hardware.get('distro', 'linux')} {hardware.get('distro_version', '')}.

IMPORTANT NOTES:
- Tailscale needs an auth key or interactive login
- AdGuard Home uses port 53 which may conflict with systemd-resolved
- OpenClaw requires a gateway token from the user
- Media servers should use the storage path: {requirements.get('storage_path', '/var/lib')} or ~/home-server-data if not specified
"""
    
    def _parse_plan(self, data: Dict) -> InstallationPlan:
        """Parse JSON response into InstallationPlan."""
        # Validate required fields
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict for plan data, got {type(data).__name__}")
        
        if 'steps' not in data:
            raise ValueError("Plan data missing required 'steps' field")
        
        steps = []
        for i, step_data in enumerate(data.get('steps', [])):
            if not isinstance(step_data, dict):
                raise ValueError(f"Step {i} is not a dict: {type(step_data).__name__}")
            
            step_number = step_data.get('step_number', i + 1)
            if not isinstance(step_number, int):
                step_number = i + 1
                
            steps.append(PlanStep(
                step_number=step_number,
                name=step_data.get('name', f'Step {step_number}'),
                description=step_data.get('description', ''),
                command=step_data.get('command'),
                commands=step_data.get('commands', []) if isinstance(step_data.get('commands'), list) else [],
                requires_sudo=bool(step_data.get('requires_sudo', False)),
                check_command=step_data.get('check_command'),
                rollback_command=step_data.get('rollback_command'),
                expected_output=step_data.get('expected_output'),
                error_hint=step_data.get('error_hint', 'Check logs for details')
            ))
        
        return InstallationPlan(
            title=data.get('title', 'Installation Plan'),
            description=data.get('description', ''),
            prerequisites=data.get('prerequisites', []),
            steps=steps,
            estimated_time_minutes=data.get('estimated_time_minutes', 30),
            known_issues=data.get('known_issues', []),
            post_install_notes=data.get('post_install_notes', [])
        )
    
    def _generate_template_plan(self, hardware: Dict, requirements: Dict) -> InstallationPlan:
        """Generate a fallback template plan if GPT fails."""
        steps = []
        step_num = 1
        
        # Get storage path with proper default
        storage = requirements.get('storage_path') or '~/home-server-data'
        storage = os.path.expanduser(storage)
        
        # Prerequisites
        if not hardware.get('has_curl'):
            steps.append(PlanStep(
                step_number=step_num,
                name="Install curl",
                description="Install curl for downloading scripts",
                command="sudo apt update && sudo apt install -y curl",
                commands=[],
                requires_sudo=True,
                check_command="curl --version",
                rollback_command=None,
                expected_output="curl",
                error_hint="Check internet connection and apt sources"
            ))
            step_num += 1
        
        # Docker installation if needed
        docker_needed = requirements.get('want_adguard') or requirements.get('want_immich') or requirements.get('want_jellyfin')
        
        if docker_needed and not hardware.get('has_docker'):
            steps.append(PlanStep(
                step_number=step_num,
                name="Install Docker",
                description="Install Docker using official script",
                command="curl -fsSL https://get.docker.com | sh",
                commands=[],
                requires_sudo=True,
                check_command="docker --version",
                rollback_command="sudo apt remove -y docker docker-engine docker.io containerd runc",
                expected_output="Docker version",
                error_hint="Check if Docker service is running: sudo systemctl status docker"
            ))
            step_num += 1
            
            steps.append(PlanStep(
                step_number=step_num,
                name="Add user to docker group",
                description="Add current user to docker group for permissionless access",
                command="sudo usermod -aG docker $USER",
                commands=[],
                requires_sudo=True,
                check_command="groups $USER | grep docker",
                rollback_command="sudo gpasswd -d $USER docker",
                expected_output="docker",
                error_hint="Log out and back in for group changes to take effect, or run 'newgrp docker'"
            ))
            step_num += 1
            
            # Note: Docker group changes require re-login, so add a warning step
            steps.append(PlanStep(
                step_number=step_num,
                name="Apply Docker group changes",
                description="Apply Docker group membership for current session",
                command="newgrp docker",
                commands=[],
                requires_sudo=False,
                check_command="docker ps",
                rollback_command=None,
                expected_output="CONTAINER",
                error_hint="If this fails, you may need to log out and log back in for Docker permissions to take effect"
            ))
            step_num += 1
        
        # Tailscale
        if requirements.get('want_tailscale'):
            steps.append(PlanStep(
                step_number=step_num,
                name="Install Tailscale",
                description="Install Tailscale VPN",
                command="curl -fsSL https://tailscale.com/install.sh | sh",
                commands=[],
                requires_sudo=True,
                check_command="tailscale version",
                rollback_command="sudo apt remove -y tailscale",
                expected_output="tailscale",
                error_hint="Check if systemd is running: systemctl status tailscaled"
            ))
            step_num += 1
            
            auth_key = requirements.get('tailscale_auth_key')
            if auth_key:
                steps.append(PlanStep(
                    step_number=step_num,
                    name="Connect Tailscale",
                    description="Connect to Tailscale network",
                    command=f"sudo tailscale up --authkey={auth_key}",
                    commands=[],
                    requires_sudo=True,
                    check_command="tailscale status",
                    rollback_command="sudo tailscale down",
                    expected_output="Connected",
                    error_hint="Check if auth key is valid and not expired"
                ))
                step_num += 1
        
        # AdGuard Home
        if requirements.get('want_adguard'):
            steps.append(PlanStep(
                step_number=step_num,
                name="Install AdGuard Home",
                description="Install AdGuard Home via Docker",
                command="docker run -d --name adguardhome --restart=always -p 53:53/tcp -p 53:53/udp -p 3000:3000 -v ~/adguardhome/work:/opt/adguardhome/work -v ~/adguardhome/conf:/opt/adguardhome/conf adguard/adguardhome",
                commands=[],
                requires_sudo=False,
                check_command="docker ps | grep adguardhome",
                rollback_command="docker stop adguardhome && docker rm adguardhome",
                expected_output="adguardhome",
                error_hint="Port 53 may be in use by systemd-resolved. Run: sudo systemctl stop systemd-resolved"
            ))
            step_num += 1
        
        # OpenClaw
        if requirements.get('want_openclaw'):
            steps.append(PlanStep(
                step_number=step_num,
                name="Install OpenClaw",
                description="Download and install OpenClaw",
                commands=[
                    "curl -fsSL https://raw.githubusercontent.com/openclaw/agent/main/install.sh | bash",
                    "openclaw --version"
                ],
                command=None,
                requires_sudo=True,
                check_command="which openclaw",
                rollback_command="sudo rm -rf /usr/local/bin/openclaw /opt/openclaw",
                expected_output="/usr/local/bin/openclaw",
                error_hint="Check installation logs in /tmp/openclaw-install.log"
            ))
            step_num += 1
        
        # Jellyfin
        if requirements.get('want_jellyfin'):
            storage = requirements.get('storage_path', '~/home-server-data')
            steps.append(PlanStep(
                step_number=step_num,
                name="Install Jellyfin",
                description="Install Jellyfin media server via Docker",
                command=f"docker run -d --name jellyfin --restart=always -p 8096:8096 -v {storage}/jellyfin/config:/config -v {storage}/jellyfin/media:/media jellyfin/jellyfin:latest",
                commands=[],
                requires_sudo=False,
                check_command="docker ps | grep jellyfin",
                rollback_command="docker stop jellyfin && docker rm jellyfin",
                expected_output="jellyfin",
                error_hint="Check if port 8096 is available"
            ))
            step_num += 1
        
        # Immich
        if requirements.get('want_immich'):
            storage = requirements.get('storage_path', '~/home-server-data')
            steps.append(PlanStep(
                step_number=step_num,
                name="Install Immich",
                description="Install Immich photo server",
                commands=[
                    f"mkdir -p {storage}/immich",
                    f"cd {storage}/immich && curl -o docker-compose.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml",
                    f"cd {storage}/immich && docker compose up -d"
                ],
                command=None,
                requires_sudo=False,
                check_command="docker ps | grep immich",
                rollback_command=f"cd {storage}/immich && docker compose down",
                expected_output="immich",
                error_hint="Check Immich logs: docker logs immich_server"
            ))
            step_num += 1
        
        return InstallationPlan(
            title="Home Server Installation Plan",
            description=f"Installs {', '.join([s.name for s in steps])}",
            prerequisites=["Root or sudo access", "Internet connection"],
            steps=steps,
            estimated_time_minutes=len(steps) * 5,
            known_issues=[
                "Port 53 conflicts with systemd-resolved for AdGuard",
                "Docker group changes require logout/login"
            ],
            post_install_notes=[
                "Access AdGuard at http://localhost:3000",
                "Access Jellyfin at http://localhost:8096",
                "Tailscale may need manual authentication if no auth key provided"
            ]
        )


def create_plan(hardware_profile: Dict, user_requirements: Dict, api_key: Optional[str] = None, ai_config: Optional[Dict] = None) -> InstallationPlan:
    """Convenience function to create plan.
    
    Args:
        hardware_profile: Detected hardware information
        user_requirements: User's selected components and preferences
        api_key: Legacy OpenAI API key (for backward compatibility)
        ai_config: Full AI provider configuration dict with provider, model, api_key, base_url
    """
    # Build AI config from requirements if available
    if not ai_config and user_requirements:
        req_ai_provider = user_requirements.get('ai_provider')
        if req_ai_provider:
            ai_config = {
                'provider': req_ai_provider,
                'model': user_requirements.get('ai_model', 'gpt-4o-mini'),
                'api_key': user_requirements.get('ai_api_key'),
                'base_url': user_requirements.get('ai_base_url')
            }
    
    engine = PlanningEngine(api_key=api_key, ai_config=ai_config)
    plan = engine.generate_plan(hardware_profile, user_requirements)
    
    # Add reverse proxy steps if domain is configured
    domain_config = user_requirements.get('domain_config')
    if domain_config and domain_config.get('enabled'):
        plan = add_reverse_proxy_steps(plan, domain_config, user_requirements)
    
    return plan


def add_reverse_proxy_steps(plan: InstallationPlan, domain_config: Dict, user_requirements: Dict) -> InstallationPlan:
    """Add reverse proxy configuration steps to the plan."""
    from copy import deepcopy
    
    plan = deepcopy(plan)
    reverse_proxy = domain_config.get('reverse_proxy', 'caddy')
    domain_name = domain_config.get('domain_name')
    
    # Calculate step number for reverse proxy (before services)
    step_num = len(plan.steps) + 1
    
    # Add reverse proxy installation step
    if reverse_proxy == 'caddy':
        plan.steps.append(PlanStep(
            step_number=step_num,
            name="Install Caddy Reverse Proxy",
            description="Install Caddy with automatic HTTPS via Let's Encrypt",
            command="sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list && sudo apt update && sudo apt install -y caddy",
            commands=[],
            requires_sudo=True,
            check_command="caddy version",
            rollback_command="sudo apt remove -y caddy && sudo rm -f /etc/apt/sources.list.d/caddy-stable.list",
            expected_output="v2.",
            error_hint="Check if GPG key import succeeded. May need to install gnupg first."
        ))
    elif reverse_proxy == 'nginx':
        plan.steps.append(PlanStep(
            step_number=step_num,
            name="Install Nginx Reverse Proxy",
            description="Install Nginx and certbot for HTTPS",
            command="sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx",
            commands=[],
            requires_sudo=True,
            check_command="nginx -v",
            rollback_command="sudo apt remove -y nginx certbot python3-certbot-nginx",
            expected_output="nginx version",
            error_hint="Check if nginx service started: sudo systemctl status nginx"
        ))
    elif reverse_proxy == 'traefik':
        plan.steps.append(PlanStep(
            step_number=step_num,
            name="Install Traefik Reverse Proxy",
            description="Install Traefik via Docker",
            command="docker pull traefik:v3.0",
            commands=[],
            requires_sudo=False,
            check_command="docker images | grep traefik",
            rollback_command="docker rmi traefik:v3.0",
            expected_output="traefik",
            error_hint="Check Docker is running and has network access"
        ))
    
    step_num += 1
    
    # Generate reverse proxy configuration
    proxy_config = generate_proxy_config(domain_config, user_requirements)
    
    plan.steps.append(PlanStep(
        step_number=step_num,
        name="Configure Reverse Proxy",
        description=f"Create {reverse_proxy} configuration for subdomains",
        commands=proxy_config['commands'],
        command=None,
        requires_sudo=True,
        check_command=proxy_config['check_command'],
        rollback_command=proxy_config['rollback_command'],
        expected_output=proxy_config['expected_output'],
        error_hint=f"Check {reverse_proxy} configuration syntax and logs"
    ))
    
    step_num += 1
    
    # Add Tailscale funnel configuration if enabled
    if domain_config.get('use_tailscale_funnel'):
        plan.steps.append(PlanStep(
            step_number=step_num,
            name="Configure Tailscale Funnel",
            description="Set up Tailscale Funnel for secure external access",
            command="sudo tailscale funnel --bg 443",
            commands=[],
            requires_sudo=True,
            check_command="sudo tailscale funnel status",
            rollback_command="sudo tailscale funnel --off",
            expected_output="Funnel",
            error_hint="Ensure Tailscale is connected and you have funnel permissions"
        ))
        step_num += 1
    
    # Add authentication middleware if required
    if domain_config.get('require_auth') and not domain_config.get('use_tailscale_funnel'):
        plan.steps.append(PlanStep(
            step_number=step_num,
            name="Configure Authentication Middleware",
            description="Set up Authelia or basic auth for domain access",
            command="docker run -d --name authelia --restart=always -p 9091:9091 -v ~/authelia/config:/config authelia/authelia:latest",
            commands=[],
            requires_sudo=False,
            check_command="docker ps | grep authelia",
            rollback_command="docker stop authelia && docker rm authelia",
            expected_output="authelia",
            error_hint="Check Authelia logs: docker logs authelia"
        ))
        step_num += 1
    
    # Add rate limiting configuration
    plan.steps.append(PlanStep(
        step_number=step_num,
        name="Configure Rate Limiting",
        description="Add rate limiting to prevent abuse",
        commands=get_rate_limit_commands(reverse_proxy),
        command=None,
        requires_sudo=True,
        check_command=None,
        rollback_command=None,
        expected_output=None,
        error_hint="Rate limiting is optional but recommended"
    ))
    
    # Add known issues and post-install notes for domain setup
    plan.known_issues.extend([
        f"DNS records must point to your server IP for {domain_name} and subdomains",
        f"Port 80 and 443 must be open for Let's Encrypt certificate issuance",
        f"CNAME records needed: {', '.join(get_configured_subdomains(domain_config))}"
    ])
    
    plan.post_install_notes.extend([
        f"Access your services at:",
        f"  - https://{domain_name}" if domain_config.get('use_for_dashboard') else None,
        f"  - https://{domain_config.get('subdomain_adguard', 'adguard')}.{domain_name}" if domain_config.get('use_for_adguard') else None,
        f"  - https://{domain_config.get('subdomain_jellyfin', 'jellyfin')}.{domain_name}" if domain_config.get('use_for_jellyfin') else None,
        f"  - https://{domain_config.get('subdomain_immich', 'photos')}.{domain_name}" if domain_config.get('use_for_immich') else None,
        "\nDNS Configuration Required:",
        f"  Create A record: {domain_name} → YOUR_SERVER_IP",
        f"  Create CNAME records for each subdomain → {domain_name}"
    ])
    
    # Remove None values from post_install_notes
    plan.post_install_notes = [n for n in plan.post_install_notes if n is not None]
    
    return plan


def get_configured_subdomains(domain_config: Dict) -> list:
    """Get list of configured subdomains."""
    subdomains = []
    domain = domain_config.get('domain_name', 'example.com')
    
    if domain_config.get('use_for_adguard'):
        subdomains.append(f"{domain_config.get('subdomain_adguard', 'adguard')}.{domain}")
    if domain_config.get('use_for_jellyfin'):
        subdomains.append(f"{domain_config.get('subdomain_jellyfin', 'jellyfin')}.{domain}")
    if domain_config.get('use_for_immich'):
        subdomains.append(f"{domain_config.get('subdomain_immich', 'photos')}.{domain}")
    if domain_config.get('use_for_dashboard'):
        subdomains.append(f"{domain_config.get('subdomain_dashboard', 'dashboard')}.{domain}")
    
    return subdomains


def generate_proxy_config(domain_config: Dict, user_requirements: Dict) -> Dict:
    """Generate reverse proxy configuration commands."""
    reverse_proxy = domain_config.get('reverse_proxy', 'caddy')
    domain = domain_config.get('domain_name')
    storage = user_requirements.get('storage_path', '~/home-server-data')
    
    if reverse_proxy == 'caddy':
        return generate_caddy_config(domain_config, domain, storage)
    elif reverse_proxy == 'nginx':
        return generate_nginx_config(domain_config, domain, storage)
    elif reverse_proxy == 'traefik':
        return generate_traefik_config(domain_config, domain, storage)
    else:
        return generate_caddy_config(domain_config, domain, storage)


def generate_caddy_config(domain_config: Dict, domain: str, storage: str) -> Dict:
    """Generate Caddy configuration."""
    config_lines = ["# Home Server Caddy Configuration", ""]
    
    # Global options
    config_lines.extend([
        "{",
        "    auto_https off",  # We'll enable per-site for control
        "    email admin@" + domain,
        "}",
        ""
    ])
    
    # Dashboard
    if domain_config.get('use_for_dashboard'):
        subdomain = domain_config.get('subdomain_dashboard', 'dashboard')
        config_lines.extend([
            f"{subdomain}.{domain} {{",
            f"    reverse_proxy localhost:8080",
            "    tls internal",
            "}",
            ""
        ])
    
    # AdGuard
    if domain_config.get('use_for_adguard'):
        subdomain = domain_config.get('subdomain_adguard', 'adguard')
        config_lines.extend([
            f"{subdomain}.{domain} {{",
            f"    reverse_proxy localhost:3000",
            "    tls internal",
            "}",
            ""
        ])
    
    # Jellyfin
    if domain_config.get('use_for_jellyfin'):
        subdomain = domain_config.get('subdomain_jellyfin', 'jellyfin')
        config_lines.extend([
            f"{subdomain}.{domain} {{",
            f"    reverse_proxy localhost:8096",
            "    tls internal",
            "}",
            ""
        ])
    
    # Immich
    if domain_config.get('use_for_immich'):
        subdomain = domain_config.get('subdomain_immich', 'photos')
        config_lines.extend([
            f"{subdomain}.{domain} {{",
            f"    reverse_proxy localhost:2283",
            "    tls internal",
            "}",
            ""
        ])
    
    config_content = "\n".join(config_lines)
    
    return {
        'commands': [
            f"echo '{config_content}' | sudo tee /etc/caddy/Caddyfile",
            "sudo systemctl reload caddy"
        ],
        'check_command': "sudo caddy validate --config /etc/caddy/Caddyfile",
        'rollback_command': "sudo rm -f /etc/caddy/Caddyfile && sudo systemctl stop caddy",
        'expected_output': 'valid'
    }


def generate_nginx_config(domain_config: Dict, domain: str, storage: str) -> Dict:
    """Generate Nginx configuration snippets."""
    commands = ["# Create Nginx site configurations"]
    
    configs = []
    
    if domain_config.get('use_for_jellyfin'):
        subdomain = domain_config.get('subdomain_jellyfin', 'jellyfin')
        configs.append((
            f"{subdomain}.{domain}",
            f"""server {{
    listen 80;
    server_name {subdomain}.{domain};
    
    location / {{
        proxy_pass http://localhost:8096;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}"""
        ))
    
    if domain_config.get('use_for_immich'):
        subdomain = domain_config.get('subdomain_immich', 'photos')
        configs.append((
            f"{subdomain}.{domain}",
            f"""server {{
    listen 80;
    server_name {subdomain}.{domain};
    
    location / {{
        proxy_pass http://localhost:2283;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}"""
        ))
    
    # Generate commands to create config files
    for server_name, config in configs:
        escaped_config = config.replace("'", "'\"'\"'")
        commands.append(f"echo '{escaped_config}' | sudo tee /etc/nginx/sites-available/{server_name}")
        commands.append(f"sudo ln -sf /etc/nginx/sites-available/{server_name} /etc/nginx/sites-enabled/")
    
    commands.append("sudo nginx -t")
    commands.append("sudo systemctl reload nginx")
    
    return {
        'commands': commands,
        'check_command': "sudo nginx -t",
        'rollback_command': "sudo rm -f /etc/nginx/sites-enabled/*.{domain} && sudo systemctl reload nginx",
        'expected_output': 'successful'
    }


def generate_traefik_config(domain_config: Dict, domain: str, storage: str) -> Dict:
    """Generate Traefik Docker Compose configuration."""
    config = f"""version: '3'
services:
  traefik:
    image: traefik:v3.0
    command:
      - --api.insecure=true
      - --providers.docker=true
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --certificatesresolvers.letsencrypt.acme.tlschallenge=true
      - --certificatesresolvers.letsencrypt.acme.email=admin@{domain}
      - --certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json
    ports:
      - 80:80
      - 443:443
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt
    networks:
      - proxy
    labels:
      - "traefik.enable=true"
"""
    
    # Add labels for each service (would be added to service containers)
    labels = []
    if domain_config.get('use_for_jellyfin'):
        subdomain = domain_config.get('subdomain_jellyfin', 'jellyfin')
        labels.append(f'      - "traefik.http.routers.jellyfin.rule=Host(`{subdomain}.{domain}`)"')
        labels.append('      - "traefik.http.routers.jellyfin.tls.certresolver=letsencrypt"')
    
    if domain_config.get('use_for_immich'):
        subdomain = domain_config.get('subdomain_immich', 'photos')
        labels.append(f'      - "traefik.http.routers.immich.rule=Host(`{subdomain}.{domain}`)"')
        labels.append('      - "traefik.http.routers.immich.tls.certresolver=letsencrypt"')
    
    return {
        'commands': [
            f"mkdir -p {storage}/traefik",
            f"echo '{config}' > {storage}/traefik/docker-compose.yml",
            f"cd {storage}/traefik && docker compose up -d"
        ],
        'check_command': f"docker ps | grep traefik",
        'rollback_command': f"cd {storage}/traefik && docker compose down",
        'expected_output': 'traefik'
    }


def get_rate_limit_commands(reverse_proxy: str) -> List[str]:
    """Get rate limiting configuration commands."""
    if reverse_proxy == 'caddy':
        return [
            "# Caddy rate limiting is configured per-site in Caddyfile",
            "# Add 'rate_limit' directive to each site block if needed"
        ]
    elif reverse_proxy == 'nginx':
        return [
            "# Add to nginx.conf http block:",
            "# limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;",
            "# Then add 'limit_req zone=general burst=20 nodelay;' to each server block"
        ]
    elif reverse_proxy == 'traefik':
        return [
            "# Traefik rate limiting is configured via middleware labels:",
            "# - 'traefik.http.middlewares.ratelimit.ratelimit.average=100'",
            "# - 'traefik.http.middlewares.ratelimit.ratelimit.burst=50'"
        ]
    return []


if __name__ == "__main__":
    # Test with sample data
    import os
    hardware = {
        "cpu_cores": 4,
        "ram_gb": 8,
        "disk_gb": {"/": 50},
        "distro": "ubuntu",
        "distro_version": "22.04",
        "has_docker": False,
        "has_curl": True
    }
    requirements = {
        "want_tailscale": True,
        "want_adguard": True,
        "want_openclaw": False,
        "storage_path": "~/home-server-data"
    }
    
    plan = create_plan(hardware, requirements)
    print(plan.to_json())

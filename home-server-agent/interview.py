"""
User Intent Interview Module
Collects user requirements through CLI prompts with validation.
"""
import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import json


@dataclass
class DomainConfig:
    """Domain configuration for custom domain support."""
    enabled: bool
    domain_name: Optional[str]
    use_for_adguard: bool
    use_for_jellyfin: bool
    use_for_immich: bool
    use_for_dashboard: bool
    subdomain_adguard: str
    subdomain_jellyfin: str
    subdomain_immich: str
    subdomain_dashboard: str
    reverse_proxy: str  # 'caddy', 'nginx', 'traefik'
    use_tailscale_funnel: bool
    require_auth: bool
    expose_externally: bool
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class UserRequirements:
    """Structured user requirements for planning engine."""
    use_cases: List[str]  # file_storage, media_server, ad_blocking, vpn, photos, backup
    media_types: List[str]  # movies, tv, music, photos
    want_tailscale: bool
    want_adguard: bool
    want_openclaw: bool
    want_immich: bool
    want_jellyfin: bool
    want_filebrowser: bool  # NEW: File manager for file storage
    storage_path: Optional[str]
    domain_name: Optional[str]
    tailscale_auth_key: Optional[str]
    openclaw_gateway_token: Optional[str]
    admin_email: Optional[str]
    notes: str
    # AI Configuration
    ai_provider: Optional[str]  # 'openai', 'anthropic', 'ollama', 'custom', None
    ai_model: Optional[str]
    ai_api_key: Optional[str]
    ai_base_url: Optional[str]
    # UI Preference
    preferred_ui: str  # 'web', 'cli', 'auto'
    # Domain Configuration
    domain_config: Optional[DomainConfig]
    # Tailscale Configuration
    tailscale_exit_node: bool
    tailscale_advertise_routes: bool
    tailscale_ssh: bool
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        if self.domain_config:
            data['domain_config'] = self.domain_config.to_dict()
        return data
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class InterviewEngine:
    """Conducts user interview to gather requirements."""

    USE_CASE_OPTIONS = {
        '1': ('file_storage', 'File storage & backup'),
        '2': ('media_server', 'Media server (movies, TV, music)'),
        '3': ('ad_blocking', 'Network-wide ad blocking'),
        '4': ('vpn', 'Secure remote access (VPN)'),
        '5': ('photos', 'Photo backup & sharing'),
        '6': ('ai_assistant', 'AI assistant / home automation'),
    }

    # Input validation patterns
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    TAILSCALE_KEY_REGEX = re.compile(r'^tskey-auth-[a-zA-Z0-9]+')
    PATH_REGEX = re.compile(r'^[~\/\.a-zA-Z0-9_-]+$')
    DOMAIN_REGEX = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
    )

    def __init__(self, use_rich: bool = True):
        self.use_rich = use_rich

    def conduct_interview(self) -> UserRequirements:
        """Run interactive interview with user."""
        self._print_header()

        # STEP 1: AI Configuration (FIRST - as requested)
        print("\n🤖 STEP 1: AI Configuration")
        print("-" * 60)
        print("The AI assistant helps create optimized installation plans.")
        print("You can use OpenAI, Anthropic Claude, or local models.\n")
        ai_config = self._ask_ai_config()

        # STEP 2: Use cases
        print("\n📋 STEP 2: What do you want to use your home server for?")
        print("-" * 60)
        use_cases = self._ask_use_cases()

        # Media types (if applicable)
        media_types = []
        if 'media_server' in use_cases or 'photos' in use_cases:
            media_types = self._ask_media_types()

        # STEP 3: Component selection with Tailscale options
        print("\n🔧 STEP 3: Component Configuration")
        print("-" * 60)
        components, tailscale_config = self._ask_components_with_tailscale(use_cases)

        # Storage path
        print("\n💾 STEP 4: Storage Configuration")
        print("-" * 60)
        storage_path = self._ask_storage_path()

        # Domain configuration
        print("\n🌐 STEP 5: Domain Configuration (Optional)")
        print("-" * 60)
        domain_config = self._ask_domain_config()

        # OpenClaw token
        openclaw_gateway_token = self._ask_optional("OpenClaw gateway token (optional): ")
        
        # Admin email
        admin_email = self._ask_email()

        # UI Preference
        preferred_ui = self._ask_ui_preference()
        
        # Additional notes
        notes = self._ask_optional("\nAny special requirements or notes? ")

        return UserRequirements(
            use_cases=use_cases,
            media_types=media_types,
            want_tailscale=components.get('tailscale', False),
            want_adguard=components.get('adguard', False),
            want_openclaw=components.get('openclaw', False),
            want_immich=components.get('immich', False),
            want_jellyfin=components.get('jellyfin', False),
            want_filebrowser=components.get('filebrowser', False),
            storage_path=storage_path,
            domain_name=domain_config.domain_name if domain_config else None,
            tailscale_auth_key=tailscale_config.get('auth_key') if tailscale_config else None,
            openclaw_gateway_token=openclaw_gateway_token or None,
            admin_email=admin_email,
            notes=notes or "",
            ai_provider=ai_config.get('provider') if ai_config else None,
            ai_model=ai_config.get('model') if ai_config else None,
            ai_api_key=ai_config.get('api_key') if ai_config else None,
            ai_base_url=ai_config.get('base_url') if ai_config else None,
            preferred_ui=preferred_ui,
            domain_config=domain_config,
            tailscale_exit_node=tailscale_config.get('enable_exit_node', False) if tailscale_config else False,
            tailscale_advertise_routes=tailscale_config.get('advertise_routes', False) if tailscale_config else False,
            tailscale_ssh=tailscale_config.get('enable_ssh', True) if tailscale_config else True
        )

    def _print_header(self):
        print("\n" + "="*60)
        print("  Home Server AI Setup - Let's understand your needs")
        print("="*60 + "\n")

    def _ask_use_cases(self) -> List[str]:
        print("What do you want to use your home server for?")
        print("(Enter numbers separated by commas, e.g., 1,3,5)")
        for key, (value, desc) in self.USE_CASE_OPTIONS.items():
            print(f"  {key}. {desc}")

        while True:
            response = input("\nYour choices: ").strip()
            if not response:
                print("Please select at least one option.")
                continue

            selections = [s.strip() for s in response.split(',')]
            use_cases = []
            for sel in selections:
                if sel in self.USE_CASE_OPTIONS:
                    use_cases.append(self.USE_CASE_OPTIONS[sel][0])
                else:
                    print(f"Invalid option: {sel}")
                    break
            else:
                return use_cases

    def _ask_media_types(self) -> List[str]:
        print("\nWhat types of media will you store?")
        print("(Enter numbers separated by commas)")
        options = {
            '1': 'movies',
            '2': 'tv',
            '3': 'music',
            '4': 'photos'
        }
        for key, value in options.items():
            print(f"  {key}. {value.title()}")

        response = input("\nYour choices: ").strip()
        selections = [s.strip() for s in response.split(',')]
        return [options[s] for s in selections if s in options]

    def _ask_components_with_tailscale(self, use_cases: List[str]) -> Tuple[Dict[str, bool], Optional[Dict]]:
        """Ask for components with detailed Tailscale configuration."""
        print("\nBased on your needs, I recommend these components:")

        components = {}
        tailscale_config = {}

        # Tailscale for VPN/remote access
        if 'vpn' in use_cases or 'file_storage' in use_cases:
            components['tailscale'] = self._ask_yes_no("Install Tailscale (secure VPN)?", default=True)
        else:
            components['tailscale'] = self._ask_yes_no("Install Tailscale (recommended for remote access)?", default=True)

        # Detailed Tailscale configuration if enabled
        if components['tailscale']:
            print("\n  ⚙️  Tailscale Configuration:")
            
            # Auth key
            print("\n  You can provide an auth key for automated setup,")
            print("  or set up Tailscale manually later.")
            auth_key = self._ask_tailscale_key()
            tailscale_config['auth_key'] = auth_key

            # Exit node configuration
            print("\n  🌐 Exit Node Configuration:")
            print("  " + "-" * 50)
            print("  An exit node allows other devices on your Tailscale")
            print("  network to route all their internet traffic through")
            print("  this server (like a VPN endpoint).")
            print("\n  ⚠️  WARNING: Enabling exit node requires:")
            print("     • IP forwarding to be enabled on this system")
            print("     • This server will handle all network traffic")
            print("     • May impact server performance")
            print("     • Check your ISP's terms of service")
            print()
            
            enable_exit_node = self._ask_yes_no(
                "  Configure this server as a Tailscale exit node?",
                default=False
            )
            tailscale_config['enable_exit_node'] = enable_exit_node

            if enable_exit_node:
                print("\n  ✅ Exit node will be configured.")
                print("  ℹ️  IP forwarding will be automatically enabled.")
                print("  ℹ️  The server will advertise routes to the Tailscale network.")
                
                # Ask about subnet routes
                print("\n  📡 Subnet Routes:")
                print("  Do you want to advertise local network routes?")
                print("  This allows other Tailscale devices to reach")
                print("  devices on your local network.")
                advertise_routes = self._ask_yes_no(
                    "  Advertise local subnet routes?",
                    default=False
                )
                tailscale_config['advertise_routes'] = advertise_routes

            # Tailscale SSH
            print("\n  🔐 Tailscale SSH:")
            print("  Allows SSH access to this server over Tailscale")
            print("  (bypasses traditional SSH port forwarding)")
            enable_ssh = self._ask_yes_no(
                "  Enable Tailscale SSH?",
                default=True
            )
            tailscale_config['enable_ssh'] = enable_ssh

            # Funnel (for domain configuration)
            print("\n  🌍 Tailscale Funnel:")
            print("  Exposes services publicly via Tailscale's servers")
            print("  (alternative to port forwarding)")
            enable_funnel = self._ask_yes_no(
                "  Enable Tailscale Funnel?",
                default=False
            )
            tailscale_config['enable_funnel'] = enable_funnel

            # Summary
            print("\n  📋 Tailscale Configuration Summary:")
            print(f"     • Exit Node: {'Yes' if enable_exit_node else 'No'}")
            print(f"     • Advertise Routes: {'Yes' if tailscale_config.get('advertise_routes') else 'No'}")
            print(f"     • Tailscale SSH: {'Yes' if enable_ssh else 'No'}")
            print(f"     • Funnel: {'Yes' if enable_funnel else 'No'}")
            print(f"     • Auth Key: {'Provided' if auth_key else 'Manual setup'}")

        # AdGuard for ad blocking
        if 'ad_blocking' in use_cases:
            components['adguard'] = self._ask_yes_no("Install AdGuard Home (network ad blocker)?", default=True)
        else:
            components['adguard'] = self._ask_yes_no("Install AdGuard Home (blocks ads network-wide)?", default=False)

        # OpenClaw for AI assistant
        if 'ai_assistant' in use_cases:
            components['openclaw'] = self._ask_yes_no("Install OpenClaw (AI assistant framework)?", default=True)
        else:
            components['openclaw'] = self._ask_yes_no("Install OpenClaw (AI assistant - can add later)?", default=False)

        # Media servers
        if 'media_server' in use_cases:
            if 'movies' in use_cases or 'tv' in use_cases:
                components['jellyfin'] = self._ask_yes_no("Install Jellyfin (movies & TV streaming)?", default=True)
            if 'photos' in use_cases:
                components['immich'] = self._ask_yes_no("Install Immich (photo backup & sharing)?", default=True)

        # FileBrowser for file storage (Apache 2.0 license - safe)
        if 'file_storage' in use_cases:
            components['filebrowser'] = self._ask_yes_no(
                "Install FileBrowser (web file manager)?\n"
                "   📁 Web-based file management\n"
                "   📤 Upload/download files\n"
                "   🔗 Share files via links\n"
                "   (Apache 2.0 licensed - safe to use)",
                default=True
            )

        return components, tailscale_config

    def _ask_storage_path(self) -> Optional[str]:
        print("\nWhere should media/data be stored?")
        print("  1. Default location (/var/lib)")
        print("  2. External drive (specify path)")
        print("  3. Home directory (~/.home-server)")

        choice = input("Choice [1]: ").strip() or "1"

        if choice == "2":
            return self._validate_and_get_custom_path()
        elif choice == "3":
            return "~/.home-server"
        return None
    
    def _validate_and_get_custom_path(self) -> Optional[str]:
        """Get and validate custom storage path with comprehensive checks."""
        max_attempts = 3
        for attempt in range(max_attempts):
            path = input("Enter mount path (e.g., /mnt/storage): ").strip()
            if not path:
                return None
            
            # Check path length
            if len(path) > 4096:  # Linux PATH_MAX is typically 4096
                print("   ⚠️ Path too long (max 4096 characters)")
                continue

            # Check for null bytes (security)
            if '\x00' in path:
                print("   ⚠️ Invalid path contains null bytes")
                continue
            
            # Check for shell metacharacters
            dangerous_chars = set(';|&$`\\<>!')
            if any(c in path for c in dangerous_chars):
                print("   ⚠️ Path contains potentially dangerous characters")
                print(f"   Avoid: {dangerous_chars}")
                if attempt < max_attempts - 1:
                    continue
                print(f"   Skipping custom path after {max_attempts} failed attempts")
                return None
            
            # Check for parent directory traversal
            if '..' in path:
                print("   ⚠️ Path cannot contain parent directory references (..)")
                continue
            
            # Basic path validation
            if not self.PATH_REGEX.match(path):
                print("   ⚠️ Invalid path format")
                print("   Use: letters, numbers, underscores, dashes, forward slashes")
                if attempt < max_attempts - 1:
                    retry = input("   Try again? [Y/n]: ").strip().lower()
                    if retry == 'n':
                        return None
                continue
            
            # Check if path looks like a URL or has common mistakes
            if path.startswith('http://') or path.startswith('https://'):
                print("   ⚠️ That looks like a URL, not a local path")
                continue
            if ' ' in path:
                print("   ⚠️ Path contains spaces - this may cause issues")
                confirm = input("   Use anyway? [y/N]: ").strip().lower()
                if confirm != 'y':
                    continue
            
            # Path looks valid
            return path
        
        print(f"   Skipping custom path after {max_attempts} failed attempts")
        return None

    def _ask_domain_config(self) -> Optional[DomainConfig]:
        """Ask for domain configuration with detailed options."""
        has_domain = self._ask_yes_no("\nDo you have a custom domain? (e.g., example.com)", default=False)
        
        if not has_domain:
            return None

        domain = self._ask_domain_name()
        if not domain:
            return None

        print("\n🌐 Reverse Proxy Setup")
        print("-" * 40)
        print("A reverse proxy handles HTTPS and routes traffic to services.")
        print("Options:")
        print("  1. Caddy (easiest, auto HTTPS)")
        print("  2. Nginx (most popular)")
        print("  3. Traefik (Docker-native)")
        print("  4. Skip (use IP:port directly)")

        proxy_choice = input("Choice [1]: ").strip() or "1"
        proxy_map = {'1': 'caddy', '2': 'nginx', '3': 'traefik', '4': None}
        reverse_proxy = proxy_map.get(proxy_choice, 'caddy')

        if not reverse_proxy:
            print("   Skipping reverse proxy setup.")
            return DomainConfig(
                enabled=True,
                domain_name=domain,
                use_for_adguard=False,
                use_for_jellyfin=False,
                use_for_immich=False,
                use_for_dashboard=False,
                subdomain_adguard='adguard',
                subdomain_jellyfin='media',
                subdomain_immich='photos',
                subdomain_dashboard='dashboard',
                reverse_proxy='none',
                use_tailscale_funnel=False,
                require_auth=True,
                expose_externally=False
            )

        # Ask which services to expose
        print(f"\n📋 Which services should use {domain}?")
        use_for_adguard = self._ask_yes_no(f"  AdGuard on adguard.{domain}?", default=True)
        use_for_jellyfin = self._ask_yes_no(f"  Jellyfin on media.{domain}?", default=True)
        use_for_immich = self._ask_yes_no(f"  Immich on photos.{domain}?", default=True)
        use_for_dashboard = self._ask_yes_no(f"  Dashboard on dashboard.{domain}?", default=True)

        # Security options
        print("\n🔒 Security Options")
        use_tailscale_funnel = self._ask_yes_no(
            "Use Tailscale Funnel as additional access method?",
            default=False
        )
        require_auth = self._ask_yes_no(
            "Require authentication for external access?",
            default=True
        )
        expose_externally = self._ask_yes_no(
            "Allow external internet access (not just Tailscale)?",
            default=False
        )

        return DomainConfig(
            enabled=True,
            domain_name=domain,
            use_for_adguard=use_for_adguard,
            use_for_jellyfin=use_for_jellyfin,
            use_for_immich=use_for_immich,
            use_for_dashboard=use_for_dashboard,
            subdomain_adguard='adguard',
            subdomain_jellyfin='media',
            subdomain_immich='photos',
            subdomain_dashboard='dashboard',
            reverse_proxy=reverse_proxy,
            use_tailscale_funnel=use_tailscale_funnel,
            require_auth=require_auth,
            expose_externally=expose_externally
        )

    def _ask_domain_name(self) -> Optional[str]:
        """Ask for domain name with RFC-compliant validation."""
        max_attempts = 5
        
        # RFC 1123 compliant domain regex (simplified but effective)
        domain_pattern = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+'  # subdomains
            r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])$'  # TLD
        )
        
        for attempt in range(max_attempts):
            domain = input("Domain name (e.g., example.com): ").strip().lower()
            
            if not domain:
                return None
            
            # Length check (total max 253, label max 63)
            if len(domain) > 253:
                print("   ⚠️ Domain too long (max 253 characters)")
                continue
            
            # Check for common mistakes
            if domain.startswith('http://') or domain.startswith('https://'):
                print("   ⚠️ Remove http:// or https:// prefix")
                domain = domain.split('://', 1)[1]
            
            if '/' in domain:
                print("   ⚠️ Remove path (e.g., /page) - just domain name needed")
                domain = domain.split('/')[0]
            
            # Validate format
            if not domain_pattern.match(domain):
                print("   ⚠️ Invalid domain format")
                print("   Valid: example.com, sub.example.com")
                print("   Invalid: -example.com, example..com")
                if attempt < max_attempts - 1:
                    continue
                else:
                    print(f"   Skipping domain after {max_attempts} failed attempts")
                    return None
            
            # Check TLD exists (basic check)
            parts = domain.split('.')
            if len(parts) < 2:
                print("   ⚠️ Domain needs a TLD (e.g., .com, .org)")
                continue
            
            return domain
        
        print(f"   Skipping domain after {max_attempts} failed attempts")
        return None

    def _ask_ai_config(self) -> Optional[Dict]:
        """Ask for AI provider configuration with better UX."""
        try:
            from ai_provider import PROVIDER_PRESETS, get_ai_config_from_env
        except ImportError as e:
            print(f"\n⚠️  AI provider module not available: {e}")
            print("   Will use template plans instead.")
            return None
        
        print("\n🤖 AI Configuration")
        print("-" * 60)
        print("The AI assistant helps create optimized installation plans.")
        print("You can use OpenAI, Anthropic Claude, or local models via Ollama.")
        print("\n💡 Press Enter to skip and use template plans instead.")
        print("   (Template plans work great - AI is optional!)\n")
        
        # Check if already configured in environment
        try:
            env_config = get_ai_config_from_env()
        except Exception as e:
            print(f"   ⚠️  Error checking environment: {e}")
            env_config = None
        
        if env_config and env_config.api_key:
            print(f"✓ Found AI configuration in environment ({env_config.provider})")
            use_env = self._ask_yes_no(f"Use {env_config.provider} configuration from environment?", default=True)
            if use_env:
                return {
                    'provider': env_config.provider,
                    'model': env_config.model,
                    'api_key': env_config.api_key,
                    'base_url': env_config.base_url
                }
        
        print("Available AI providers:")
        for key, preset in PROVIDER_PRESETS.items():
            print(f"  {key:12} - {preset['name']}")
            if 'docs_url' in preset:
                print(f"               Get key: {preset['docs_url']}")
        
        print("\nSelect a provider (or press Enter to skip):")
        choice = input("> ").strip().lower()
        
        if not choice:
            print("   ✓ Skipping AI configuration. Will use template plans.")
            return None
        
        if choice not in PROVIDER_PRESETS:
            print(f"   Unknown provider '{choice}'. Using template plans.")
            return None
        
        preset = PROVIDER_PRESETS[choice]
        
        # Show available models
        print(f"\nAvailable models for {preset['name']}:")
        for i, model in enumerate(preset['models'], 1):
            default_marker = " (recommended)" if model == preset['default_model'] else ""
            print(f"  {i}. {model}{default_marker}")
        
        print("\nSelect model (number or name, Enter for recommended):")
        model_choice = input("> ").strip()
        
        model = preset['default_model']  # Default
        if model_choice.isdigit():
            idx = int(model_choice) - 1
            if 0 <= idx < len(preset['models']):
                model = preset['models'][idx]
            else:
                print(f"   Invalid selection, using recommended: {model}")
        elif model_choice:
            # Validate custom model name (basic sanity check)
            if len(model_choice) > 100:
                print("   Model name too long, using recommended")
            else:
                model = model_choice
        
        # Get API key
        api_key = None
        if preset.get('env_key'):
            env_value = os.getenv(preset['env_key'])
            if env_value:
                print(f"\n✓ Found {preset['env_key']} in environment")
                api_key = env_value
            else:
                print(f"\n💡 API Key (optional - press Enter to skip):")
                if 'docs_url' in preset:
                    print(f"   Get one at: {preset['docs_url']}")
                api_key_input = input("> ").strip()
                # Basic API key validation
                if api_key_input:
                    if len(api_key_input) < 10:
                        print("   ⚠️  API key seems short, please verify")
                    api_key = api_key_input
        
        # Get base URL for custom endpoints
        base_url = preset.get('base_url')
        if choice == 'custom' or choice == 'ollama':
            print(f"\nEnter the API base URL (default: {base_url or 'none'}):")
            custom_url = input("> ").strip()
            if custom_url:
                base_url = custom_url
        
        if not api_key and choice not in ['ollama', 'custom']:
            print("   No API key provided. Using template plans.")
            return None
        
        return {
            'provider': choice,
            'model': model,
            'api_key': api_key,
            'base_url': base_url
        }

    def _ask_ui_preference(self) -> str:
        """Ask user for UI preference."""
        print("\n🖥️  Interface Preference")
        print("  1. Web UI (browser-based, easier)")
        print("  2. Terminal/CLI (text-based, works over SSH)")
        print("  3. Auto (choose based on environment)")

        choice = input("Choice [1]: ").strip() or "1"

        ui_map = {'1': 'web', '2': 'cli', '3': 'auto'}
        return ui_map.get(choice, 'web')

    def _ask_yes_no(self, prompt: str, default: bool = False) -> bool:
        """Ask a yes/no question with validation."""
        suffix = " [Y/n]: " if default else " [y/N]: "
        while True:
            response = input(prompt + suffix).strip().lower()
            if not response:
                return default
            if response in ('y', 'yes'):
                return True
            if response in ('n', 'no'):
                return False
            print("   Please answer 'y' or 'n'")

    def _ask_optional(self, prompt: str) -> Optional[str]:
        """Ask for optional input."""
        response = input(prompt).strip()
        return response if response else None

    def _ask_email(self) -> Optional[str]:
        """Ask for email with validation and attempt limit."""
        max_attempts = 3
        for attempt in range(max_attempts):
            email = input("Admin email (for notifications): ").strip()
            if not email:
                return None
            if self.EMAIL_REGEX.match(email):
                return email
            print("   ⚠️ Invalid email format")
            if attempt < max_attempts - 1:
                print(f"   ({max_attempts - attempt - 1} attempts remaining)")
        print(f"   Skipping email after {max_attempts} failed attempts")
        return None

    def _ask_tailscale_key(self) -> Optional[str]:
        """Ask for Tailscale auth key with guidance and easy skip option."""
        print("\n   💡 About Tailscale Auth Keys:")
        print("      Auth keys allow automatic device connection.")
        print("      Don't have one? You can:")
        print("      1. Get one at: https://login.tailscale.com/admin/settings/keys")
        print("      2. Or press Enter to set up manually later")
        print("      3. Or type 'skip' to configure later\n")
        
        max_attempts = 3
        for attempt in range(max_attempts):
            key = input("   Tailscale auth key (tskey-auth-... or 'skip'): ").strip()
            
            # Allow easy skip
            if not key or key.lower() in ('skip', 'none', 'later', 'n', 'no'):
                print("   ✓ Will configure Tailscale manually later")
                return None
            
            # Basic length check
            if len(key) > 500:
                print("   ⚠️  Key too long (max 500 characters)")
                continue
            
            # Validate format
            if self.TAILSCALE_KEY_REGEX.match(key):
                print("   ✓ Valid auth key provided")
                return key
            
            print("   ⚠️  Invalid format. Should start with 'tskey-auth-'")
            
            # On last attempt, give up gracefully
            if attempt >= max_attempts - 1:
                print("   ✓ Will configure manually later")
                return None
            
            # Ask if they want to try again or skip
            retry = input("   Try again or skip? [retry/skip]: ").strip().lower()
            if retry in ('skip', 's', 'no', 'n'):
                print("   ✓ Will configure manually later")
                return None
        
        return None
        return None


def conduct_interview() -> UserRequirements:
    """Convenience function to run interview."""
    engine = InterviewEngine()
    return engine.conduct_interview()


if __name__ == "__main__":
    requirements = conduct_interview()
    print("\n" + "="*60)
    print("Your Configuration:")
    print("="*60)
    print(requirements.to_json())
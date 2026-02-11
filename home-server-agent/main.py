#!/usr/bin/env python3
"""
Home Server AI Setup Agent - FIXED VERSION
Main entry point with improved UX and bug fixes.
"""
import os
import sys
import json
import argparse
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Version info
__version__ = "1.0.0"
__author__ = "Home Server AI Team"

# Import modules
from hardware_detector import detect_hardware, HardwareProfile
from interview import conduct_interview, UserRequirements, InterviewEngine
from planner import create_plan, InstallationPlan
from executor import ExecutionEngine, StateManager
from error_recovery import ErrorRecoveryEngine
from web_config import WebConfigServer
from preflight import run_preflight_checks
from config_validator import validate_config_file, validate_requirements

# Setup logging with rotation
from logging.handlers import RotatingFileHandler
import signal
import atexit

# Global state for cleanup
_state_manager = None
_web_server = None

def _cleanup():
    """Cleanup function called on exit."""
    global _state_manager, _web_server
    if _state_manager:
        try:
            _state_manager.close()
        except Exception:
            pass

def _signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    print("\n\n⚠️  Received interrupt signal, cleaning up...")
    _cleanup()
    sys.exit(130)

# Register cleanup handlers
atexit.register(_cleanup)
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# Setup logging with rotation
log_handler = RotatingFileHandler('setup.log', maxBytes=5*1024*1024, backupCount=3)
log_handler.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[log_handler, console_handler]
)
logger = logging.getLogger(__name__)


def print_header():
    """Print beautiful header."""
    print("\n" + "="*70)
    print("  🏠 Home Server AI Setup Agent")
    print("  Your AI-powered home server installer")
    print("="*70)
    print()


def print_section(title: str, icon: str = "📋"):
    """Print section header."""
    print(f"\n{icon} {title}")
    print("-"*70)


def print_success(message: str):
    """Print success message."""
    print(f"   ✅ {message}")


def print_warning(message: str):
    """Print warning message."""
    print(f"   ⚠️  {message}")


def print_error(message: str):
    """Print error message."""
    print(f"   ❌ {message}")


def print_info(message: str):
    """Print info message."""
    print(f"   ℹ️  {message}")


def load_or_create_config(path: str = "config.json", prefer_existing: bool = True) -> Optional[Dict[str, Any]]:
    """
    Load configuration from file or guide user to create one.
    
    Args:
        path: Path to config file
        prefer_existing: If True, prefer existing config over new interview
    
    Returns:
        Configuration dict or None
    """
    config = None
    
    if os.path.exists(path) and prefer_existing:
        print_section("Loading Configuration", "📂")
        print_info(f"Found existing configuration: {path}")
        
        try:
            with open(path, 'r') as f:
                config = json.load(f)
            
            # Show summary
            print_info(f"AI Provider: {config.get('ai_provider', 'None (templates)')}")
            print_info(f"Use Cases: {', '.join(config.get('use_cases', []))}")
            print_info(f"Storage: {config.get('storage_path', '/var/lib')}")
            
            # Ask to use or recreate
            use_existing = input("\nUse this configuration? [Y/n]: ").strip().lower()
            if not use_existing or use_existing in ['y', 'yes']:
                print_success("Using existing configuration")
                return config
            else:
                print_info("Will create new configuration")
                config = None
        except (json.JSONDecodeError, IOError) as e:
            print_error(f"Could not read config file: {e}")
            config = None
    
    return config


def run_cli_interview() -> Dict[str, Any]:
    """
    Run CLI interview with improved UX.
    """
    print_section("Configuration", "⚙️")
    print("Let's set up your home server. You can skip optional fields by pressing Enter.\n")
    
    engine = InterviewEngine()
    requirements = engine.conduct_interview()
    return requirements.to_dict()


def run_web_interface(port: int = 8080) -> Optional[Dict[str, Any]]:
    """
    Run web interface and get configuration.
    
    Returns:
        Configuration dict or None if cancelled/timeout
    """
    print_section("Web Configuration", "🌐")
    print_info(f"Starting web server on port {port}")
    print_info(f"Open http://localhost:{port} in your browser")
    print_info("Press Ctrl+C to cancel\n")
    
    server = WebConfigServer(port=port, config_file="config.json")
    global _web_server
    _web_server = server
    
    try:
        # Start server without blocking parameter
        import threading
        thread = threading.Thread(target=server.run)
        thread.daemon = True
        thread.start()
        
        # Wait for config
        config = server.wait_for_config(timeout=300)
        
        if config:
            print_success("Configuration received from web interface")
            return config
        else:
            print_error("Configuration timeout or cancelled")
            return None
            
    except Exception as e:
        print_error(f"Web interface error: {e}")
        return None


def run_setup_flow(args) -> int:
    """
    Main setup flow with improved UX.
    
    Returns:
        Exit code (0 for success)
    """
    global _state_manager
    
    print_header()
    
    # Generate session ID
    session_id = str(uuid.uuid4())[:8]
    print_info(f"Session ID: {session_id}")
    print_info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize state manager
    _state_manager = StateManager()
    state = _state_manager
    
    # Check for resume
    if args.resume:
        print_section("Resuming Session", "🔄")
        # ... resume logic ...
        return 0
    
    # Step 1: Hardware Detection
    print_section("Hardware Detection", "🔍")
    try:
        hardware_profile = detect_hardware()
        print_info(f"CPU: {hardware_profile.cpu_model} ({hardware_profile.cpu_cores} cores)")
        print_info(f"RAM: {hardware_profile.ram_gb:.1f} GB")
        print_info(f"Disk: {hardware_profile.disk_gb}")
        print_info(f"OS: {hardware_profile.distro} {hardware_profile.distro_version}")
        
        if hardware_profile.potential_issues:
            print("\n   ⚠️  Potential issues detected:")
            for issue in hardware_profile.potential_issues:
                print(f"      - {issue}")
        
        hardware = hardware_profile.to_dict()
        print_success("Hardware detection complete")
    except Exception as e:
        print_warning(f"Hardware detection failed: {e}")
        print_info("Using default hardware profile")
        hardware = {
            'cpu_cores': 2,
            'cpu_threads': 4,
            'cpu_model': 'Unknown',
            'ram_gb': 4.0,
            'disk_gb': {'/': 50.0},
            'distro': 'unknown',
            'has_docker': False,
            'has_curl': True
        }
    
    # Step 2: Get Configuration
    print_section("Configuration", "⚙️")
    
    requirements = None
    
    # Try to load existing config first
    if not args.no_config and os.path.exists("config.json"):
        requirements = load_or_create_config("config.json", prefer_existing=True)
    
    # If no config or user wants new one
    if not requirements:
        if args.web:
            # Use web interface
            requirements = run_web_interface(port=args.port)
            if not requirements:
                print_error("Web configuration failed")
                return 1
        else:
            # Use CLI interview
            requirements = run_cli_interview()
    
    if not requirements:
        print_error("No configuration obtained")
        return 1
    
    # Validate requirements
    is_valid, errors, warnings = validate_requirements(requirements)
    if not is_valid:
        print_error("Configuration validation failed:")
        for error in errors:
            print(f"   - {error}")
        return 1
    
    if warnings:
        print_warning("Configuration warnings:")
        for warning in warnings:
            print(f"   - {warning}")
    
    print_success(f"Configuration complete: {', '.join(requirements.get('use_cases', []))}")
    
    # Step 3: Generate Plan
    print_section("Installation Plan", "📝")
    
    ai_provider = requirements.get('ai_provider')
    if ai_provider and ai_provider != 'none':
        print_info(f"Using AI: {ai_provider} ({requirements.get('ai_model', 'default')})")
    else:
        print_info("Using template-based installation (no AI)")
    
    try:
        plan_obj = create_plan(hardware, requirements)
        plan = plan_obj.to_dict()
        
        print_info(f"Plan: {plan['title']}")
        print_info(f"Steps: {len(plan['steps'])}")
        print_info(f"Est. time: {plan['estimated_time_minutes']} minutes")
        
        if plan.get('known_issues'):
            print("\n   ⚠️  Known issues:")
            for issue in plan['known_issues']:
                print(f"      - {issue}")
        
        print_success("Plan generated")
    except Exception as e:
        print_error(f"Plan generation failed: {e}")
        return 1
    
    # Save session
    state.create_session(session_id, hardware, requirements, plan)
    
    # Plan only mode
    if args.plan_only:
        print_section("Plan Only Mode", "📋")
        print(json.dumps(plan, indent=2))
        return 0
    
    # Pre-flight checks
    print_section("Pre-flight Checks", "✅")
    storage_path = requirements.get('storage_path')
    if not run_preflight_checks(storage_path):
        print_error("Pre-flight checks failed. Fix issues and try again.")
        return 1
    print_success("Pre-flight checks passed")
    
    # Execute plan
    print_section("Installation", "🚀")
    
    if not args.yes:
        confirm = input("\nProceed with installation? [Y/n]: ").strip().lower()
        if confirm and confirm not in ['y', 'yes']:
            print_info("Installation cancelled")
            return 0
    
    executor = ExecutionEngine(
        state_manager=state,
        dry_run=args.dry_run,
        auto_approve=args.yes
    )
    executor.session_id = session_id
    
    print(f"\n   📊 Progress: 0/{len(plan['steps'])} steps\n")
    
    results = executor.execute_plan(plan, resume_from=args.resume_step or 0)
    
    # Summary
    print_section("Installation Summary", "📊")
    success_count = sum(1 for r in results if r.success)
    total = len(results)
    
    print_info(f"Completed: {success_count}/{total} steps")
    
    if success_count == total:
        print_success("Installation complete!")
        print("\n   🎉 Your home server is ready!")
        print("\n   Access your services:")
        print("   • AdGuard:      http://localhost:3000")
        print("   • Jellyfin:     http://localhost:8096")
        print("   • Immich:       http://localhost:2283")
        print("   • FileBrowser:  http://localhost:8082")
        print("   • Dashboard:    http://localhost:8081")
        return 0
    else:
        print_warning(f"Installation incomplete: {total - success_count} steps failed")
        print_info(f"Resume with: python main.py --resume {session_id}")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Home Server AI Setup Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Interactive setup
  python main.py --web              # Use web interface
  python main.py --dry-run          # Test without installing
  python main.py --resume ABC123    # Resume interrupted session
        """
    )
    
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--dry-run', action='store_true', help='Test without making changes')
    parser.add_argument('--web', action='store_true', help='Use web interface for configuration')
    parser.add_argument('--port', type=int, default=8080, help='Port for web interface (default: 8080)')
    parser.add_argument('--config', type=str, help='Load config from file')
    parser.add_argument('--no-config', action='store_true', help='Ignore existing config.json')
    parser.add_argument('--plan-only', action='store_true', help='Generate plan only, do not execute')
    parser.add_argument('--resume', type=str, help='Resume session by ID')
    parser.add_argument('--resume-step', type=int, help='Resume from specific step')
    parser.add_argument('-y', '--yes', action='store_true', help='Auto-approve all prompts')
    
    args = parser.parse_args()
    
    try:
        exit_code = run_setup_flow(args)
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logger.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()

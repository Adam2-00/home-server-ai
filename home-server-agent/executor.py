"""
Execution Engine
Executes commands from the installation plan safely.
"""
import subprocess
import time
import json
import sqlite3
import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Import error recovery at module level to avoid repeated imports
from error_recovery import ErrorRecoveryEngine

# Module logger
logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a command execution."""
    success: bool
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'returncode': self.returncode,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'duration_ms': self.duration_ms,
            'timestamp': self.timestamp
        }


class StateManager:
    """Manages execution state with SQLite persistence."""
    
    def __init__(self, db_path: str = "state.db"):
        self.db_path = db_path
        self._connection = None
        self._init_db()
    
    def _get_connection(self):
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
        return self._connection
    
    def _init_db(self):
        """Initialize database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS execution_state (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                step_number INTEGER,
                step_name TEXT,
                status TEXT,
                result_json TEXT,
                timestamp TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                session_id TEXT UNIQUE,
                hardware_profile TEXT,
                user_requirements TEXT,
                plan_json TEXT,
                current_step INTEGER DEFAULT 0,
                status TEXT DEFAULT 'in_progress',
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        conn.commit()
    
    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    def __del__(self):
        """Destructor to ensure connection is closed."""
        self.close()
    
    def create_session(self, session_id: str, hardware: Dict, requirements: Dict, plan: Dict) -> str:
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT OR REPLACE INTO sessions 
            (session_id, hardware_profile, user_requirements, plan_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, json.dumps(hardware), json.dumps(requirements), 
              json.dumps(plan), now, now))
        conn.commit()
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,))
        row = cursor.fetchone()
        if row:
            return {
                'session_id': row[1],
                'hardware_profile': json.loads(row[2]),
                'user_requirements': json.loads(row[3]),
                'plan_json': json.loads(row[4]),
                'current_step': row[5],
                'status': row[6]
            }
        return None
    
    def update_step(self, session_id: str, step_number: int, step_name: str, 
                    status: str, result: Optional[ExecutionResult] = None):
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        result_json = json.dumps(result.to_dict()) if result else None
        cursor.execute('''
            INSERT INTO execution_state (session_id, step_number, step_name, status, result_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, step_number, step_name, status, result_json, now))
        
        cursor.execute('''
            UPDATE sessions SET current_step = ?, updated_at = ? WHERE session_id = ?
        ''', (step_number, now, session_id))
        
        conn.commit()
    
    def get_completed_steps(self, session_id: str) -> List[int]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT step_number FROM execution_state 
            WHERE session_id = ? AND status = 'completed'
        ''', (session_id,))
        rows = cursor.fetchall()
        return [r[0] for r in rows]
    
    def complete_session(self, session_id: str, success: bool = True):
        conn = self._get_connection()
        cursor = conn.cursor()
        status = 'completed' if success else 'failed'
        cursor.execute('''
            UPDATE sessions SET status = ?, updated_at = ? WHERE session_id = ?
        ''', (status, datetime.now().isoformat(), session_id))
        conn.commit()


class ExecutionEngine:
    """Executes installation plan steps with safety checks."""
    
    DANGEROUS_PATTERNS = [
        'rm -rf /',
        'rm -rf /*',
        'mkfs',
        'dd if=/dev/zero',
        ':(){ :|:& };:',  # Fork bomb
        '> /dev/sda',
        '>/dev/sda',
        'mv /* /dev/null',
        'chmod -R 777 /',
        'chmod -R 777 /*',
        'mkfs.ext4 /dev/sda',
        'mkfs.xfs /dev/sda',
        'mkfs.btrfs /dev/sda',
        'dd of=/dev/sda',
        'dd if=/dev/random of=/dev/sda',
        'dd if=/dev/urandom of=/dev/sda',
        'shred /dev/sda',
        'echo "* * * * * rm -rf /" | crontab',  # Cron-based destruction
    ]
    
    # Pre-compiled regex patterns for command sanitization (performance optimization)
    _SANITIZATION_PATTERNS = [
        (re.compile(r'(authkey=)([^\s&]+)'), r'\1***MASKED***'),
        (re.compile(r'(api[_-]?key[=:]\s*)([^\s&]+)', re.IGNORECASE), r'\1***MASKED***'),
        (re.compile(r'(password[=:]\s*)([^\s&]+)', re.IGNORECASE), r'\1***MASKED***'),
        (re.compile(r'(token[=:]\s*)([^\s&]+)', re.IGNORECASE), r'\1***MASKED***'),
        (re.compile(r'(tskey-auth-)[a-zA-Z0-9]+'), r'\1***MASKED***'),
        (re.compile(r'(ocgw-)[a-zA-Z0-9]+'), r'\1***MASKED***'),
    ]
    
    def __init__(self, state_manager: Optional[StateManager] = None, 
                 dry_run: bool = False, auto_approve: bool = False):
        self.state = state_manager or StateManager()
        self.dry_run = dry_run
        self.auto_approve = auto_approve
        self.session_id: Optional[str] = None
    
    def start_session(self, session_id: str, hardware: Dict, requirements: Dict, plan: Dict):
        """Initialize a new execution session."""
        self.session_id = self.state.create_session(session_id, hardware, requirements, plan)
    
    def validate_command(self, command: str) -> Tuple[bool, str]:
        """Check if command is safe to execute."""
        if not command or not command.strip():
            return False, "Empty command"
        
        cmd_lower = command.lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in cmd_lower:
                return False, f"Command contains dangerous pattern: {pattern}"
        
        return True, "OK"
    
    def execute_step(self, step: Dict, timeout: int = 300) -> ExecutionResult:
        """Execute a single plan step."""
        if not self.session_id:
            raise ValueError("No active session. Call start_session() first.")
        
        step_number = step.get('step_number', 0)
        step_name = step.get('name', 'Unknown')
        commands = []
        
        if step.get('command'):
            commands.append(step['command'])
        commands.extend(step.get('commands', []))
        
        # Handle empty command list
        if not commands:
            result = ExecutionResult(
                success=True, returncode=0,
                stdout="", stderr="",
                duration_ms=0, timestamp=datetime.now().isoformat()
            )
            self.state.update_step(self.session_id, step_number, step_name, 'completed', result)
            return result
        
        print(f"\n[Step {step_number}] {step_name}")
        print(f"Description: {step.get('description', '')}")
        
        for cmd in commands:
            print(f"\nCommand: {cmd}")
            
            # Validate
            safe, reason = self.validate_command(cmd)
            if not safe:
                result = ExecutionResult(
                    success=False, returncode=-1,
                    stdout="", stderr=f"Validation failed: {reason}",
                    duration_ms=0, timestamp=datetime.now().isoformat()
                )
                self.state.update_step(self.session_id, step_number, step_name, 'failed', result)
                return result
            
            # Confirm if needed
            if not self.auto_approve and step.get('requires_sudo', False):
                confirm = input("This step requires sudo. Execute? [Y/n]: ").strip().lower()
                if confirm and confirm not in ['y', 'yes']:
                    result = ExecutionResult(
                        success=False, returncode=-1,
                        stdout="", stderr="User cancelled",
                        duration_ms=0, timestamp=datetime.now().isoformat()
                    )
                    self.state.update_step(self.session_id, step_number, step_name, 'cancelled', result)
                    return result
            
            # Execute
            if self.dry_run:
                print("  [DRY RUN] Would execute:", cmd)
                result = ExecutionResult(
                    success=True, returncode=0,
                    stdout="[DRY RUN]", stderr="",
                    duration_ms=0, timestamp=datetime.now().isoformat()
                )
            else:
                result = self._run_command(cmd, timeout)
                print(f"  Return code: {result.returncode}")
                if result.stdout:
                    print(f"  Output: {result.stdout[:200]}..." if len(result.stdout) > 200 else f"  Output: {result.stdout}")
                if result.stderr and not result.success:
                    print(f"  Error: {result.stderr[:200]}..." if len(result.stderr) > 200 else f"  Error: {result.stderr}")
            
            if not result.success:
                self.state.update_step(self.session_id, step_number, step_name, 'failed', result)
                return result
        
        # Run verification check if provided
        if step.get('check_command') and not self.dry_run:
            check_cmd = step['check_command']
            print(f"\nVerifying: {check_cmd}")
            check_result = self._run_command(check_cmd, timeout=30)
            if not check_result.success:
                print(f"  Warning: Verification failed")
            else:
                print(f"  ✓ Verified")
        
        self.state.update_step(self.session_id, step_number, step_name, 'completed', result)
        return result
    
    def _run_command(self, command, timeout: int) -> ExecutionResult:
        """
        Execute a shell command and capture results with comprehensive error handling.
        
        Args:
            command: Either a string (legacy) or list of strings (secure)
            timeout: Maximum execution time in seconds
        """
        from security_utils import CredentialManager
        
        # Validate timeout
        if timeout <= 0 or timeout > 3600:  # Max 1 hour
            timeout = 300  # Default to 5 minutes
            logger.warning(f"Invalid timeout provided, defaulting to 300s for command: {str(command)[:50]}...")
        
        # Handle both string and list commands
        if isinstance(command, list):
            # Secure: list of arguments, no shell needed
            shell = False
            cmd_to_execute = command
            cmd_for_logging = ' '.join(command)
        elif isinstance(command, str):
            # Legacy: string command, requires shell
            if not command.strip():
                return ExecutionResult(
                    success=False, returncode=-1,
                    stdout="", stderr="Empty command provided",
                    duration_ms=0, timestamp=datetime.now().isoformat()
                )
            shell = True
            cmd_to_execute = command
            cmd_for_logging = command
        else:
            return ExecutionResult(
                success=False, returncode=-1,
                stdout="", stderr="Invalid command type",
                duration_ms=0, timestamp=datetime.now().isoformat()
            )
        
        start = time.time()
        
        try:
            # Pre-execution: log command details (without sensitive data)
            safe_cmd = CredentialManager.sanitize_command_for_logging(cmd_for_logging)
            logger.info(f"Executing: {safe_cmd}")
            
            result = subprocess.run(
                cmd_to_execute,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                # Prevent fork bombs and resource exhaustion
                preexec_fn=self._set_process_limits if os.name != 'nt' else None
            )
            duration = int((time.time() - start) * 1000)
            
            success = result.returncode == 0
            if not success:
                logger.warning(f"Command failed with exit code {result.returncode}: {safe_cmd}")
                # Log stderr for debugging (truncated)
                stderr_preview = result.stderr[:500] if result.stderr else "(no stderr)"
                logger.debug(f"Failed command stderr: {stderr_preview}")
            else:
                logger.debug(f"Command succeeded in {duration}ms: {safe_cmd}")
            
            return ExecutionResult(
                success=success,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration,
                timestamp=datetime.now().isoformat()
            )
            
            return ExecutionResult(
                success=success,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration,
                timestamp=datetime.now().isoformat()
            )
        except subprocess.TimeoutExpired:
            duration = int((time.time() - start) * 1000)
            logger.error(f"Command timed out after {timeout}s: {safe_cmd}")
            return ExecutionResult(
                success=False, returncode=-1,
                stdout="", stderr=f"Command timed out after {timeout}s",
                duration_ms=duration, timestamp=datetime.now().isoformat()
            )
        except OSError as e:
            duration = int((time.time() - start) * 1000)
            logger.error(f"OS error executing command: {e}")
            return ExecutionResult(
                success=False, returncode=-1,
                stdout="", stderr=f"OS error: {e}",
                duration_ms=duration, timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            logger.exception(f"Unexpected error executing command: {e}")
            return ExecutionResult(
                success=False, returncode=-1,
                stdout="", stderr=f"Unexpected error: {e}",
                duration_ms=duration, timestamp=datetime.now().isoformat()
            )
    
    def _sanitize_command_for_logging(self, command: str) -> str:
        """Remove sensitive data from command before logging."""
        sanitized = command
        
        # Use pre-compiled patterns for better performance
        for pattern, replacement in self._SANITIZATION_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        
        return sanitized
    
    def _set_process_limits(self):
        """Set resource limits for child processes (Linux only)."""
        try:
            import resource
            # Limit memory to 2GB to prevent runaway processes
            resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 * 1024 * 1024, resource.RLIM_INFINITY))
            # Limit CPU time to prevent infinite loops
            resource.setrlimit(resource.RLIMIT_CPU, (3600, resource.RLIM_INFINITY))
        except (ImportError, ValueError, OSError):
            # resource module not available or limits can't be set
            pass
    
    def execute_plan(self, plan: Dict, resume_from: int = 0) -> List[ExecutionResult]:
        """Execute all steps in a plan with error recovery."""
        results = []
        steps = plan.get('steps', [])
        total_steps = len(steps)
        
        # Skip already completed steps
        completed = self.state.get_completed_steps(self.session_id) if self.session_id else []
        
        print(f"\n📊 Executing {total_steps} steps...")
        if completed:
            print(f"   ({len(completed)} already completed)")
        
        for i, step in enumerate(steps):
            step_num = step.get('step_number', i)
            
            # Progress bar
            progress = (i + 1) / total_steps * 100
            bar_filled = int(40 * (i + 1) / total_steps)
            bar = '█' * bar_filled + '░' * (40 - bar_filled)
            print(f"\r   [{bar}] {i+1}/{total_steps} ({int(progress)}%)", end='', flush=True)
            
            if step_num in completed:
                print(f"\n   ✓ Step {step_num} already completed, skipping")
                continue
            
            if step_num < resume_from:
                continue
            
            result = self.execute_step(step)
            results.append(result)
            
            if not result.success:
                print(f"\n\n❌ Step {step_num} failed: {step.get('name', 'Unknown')}")
                print(f"   Error: {result.stderr[:200]}")
                
                # Attempt error recovery
                if self.state and self.session_id:
                    print("\n🔧 Attempting error recovery...")
                    
                    api_key = os.getenv('OPENAI_API_KEY')
                    recovery = ErrorRecoveryEngine(api_key)
                    
                    step_context = {
                        'step_number': step_num,
                        'step_name': step.get('name'),
                        'session_id': self.session_id
                    }
                    
                    command = step.get('command') or ' '.join(step.get('commands', []))
                    analysis = recovery.analyze_error(command, result.stdout, result.stderr, step_context)
                    
                    print(f"   Analysis: {analysis.get('analysis')}")
                    print(f"   Suggested fix: {analysis.get('suggested_fix')}")
                    
                    if analysis.get('can_auto_retry') and not self.dry_run:
                        retry = input(f"\n   Attempt automatic fix? [Y/n]: ").strip().lower()
                        if not retry or retry in ['y', 'yes']:
                            print(f"   Applying fix: {analysis.get('suggested_fix')}")
                            fix_result = self._run_command(analysis.get('suggested_fix'), timeout=60)
                            if fix_result.success:
                                print("   ✓ Fix applied, retrying original command...")
                                result = self.execute_step(step)
                                if result.success:
                                    results[-1] = result  # Update result
                                    print(f"\r   [{bar}] {i+1}/{total_steps} ({int(progress)}%)", end='', flush=True)
                                    continue
                    
                    print("\n   Halting execution. You can resume later with the fix.")
                
                break
            
            print(f"\r   [{bar}] {i+1}/{total_steps} ({int(progress)}%)", end='', flush=True)
        
        print()  # New line after progress bar
        
        # Mark session complete if all steps succeeded
        if all(r.success for r in results) and self.session_id:
            self.state.complete_session(self.session_id, success=True)
        elif self.session_id:
            self.state.complete_session(self.session_id, success=False)
        
        return results


def run_plan(plan: Dict, session_id: str, dry_run: bool = False, 
             auto_approve: bool = False) -> List[ExecutionResult]:
    """Convenience function to execute a plan."""
    engine = ExecutionEngine(dry_run=dry_run, auto_approve=auto_approve)
    # Assume session already created
    engine.session_id = session_id
    return engine.execute_plan(plan)


if __name__ == "__main__":
    # Test execution
    engine = ExecutionEngine(dry_run=True)
    test_step = {
        'step_number': 1,
        'name': 'Test',
        'description': 'Test step',
        'command': 'echo hello',
        'requires_sudo': False
    }
    result = engine.execute_step(test_step)
    print(result.to_dict())

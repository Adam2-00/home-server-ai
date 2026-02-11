"""
Error Recovery Module
Uses GPT-4 to suggest fixes for failed commands.
"""
import json
import os
from typing import Dict, List, Optional, Tuple

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class ErrorRecoveryEngine:
    """Suggests recovery strategies using GPT-4."""
    
    SYSTEM_PROMPT = """You are a Linux troubleshooting expert. Given a failed command and its error output, suggest the most likely fix.

Respond with JSON in this format:
{
  "analysis": "Brief explanation of what went wrong",
  "severity": "low|medium|high|critical",
  "suggested_fix": "The exact command or action to try",
  "fix_type": "retry|modify_command|install_dependency|manual_intervention|skip",
  "alternative_fixes": ["Other options if primary fix fails"],
  "can_auto_retry": true/false,
  "explanation_for_user": "Simple explanation for non-technical user"
}

Common issues and fixes:
- "command not found": Install the package or use full path
- "permission denied": Use sudo or check file permissions
- "port already in use": Kill process on port or use different port
- "connection refused": Check if service is running
- "no space left": Free disk space
- "docker: permission denied": User not in docker group
"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        
        # Common error patterns and fixes (fallback if no API)
        self.common_fixes = {
            'command not found': {
                'fix_type': 'install_dependency',
                'suggestion': 'Install the missing package with apt'
            },
            'permission denied': {
                'fix_type': 'modify_command',
                'suggestion': 'Try running with sudo'
            },
            'could not resolve host': {
                'fix_type': 'retry',
                'suggestion': 'Check internet connection and retry'
            },
            'port is already allocated': {
                'fix_type': 'modify_command',
                'suggestion': 'Stop the existing service or use a different port'
            },
            'bind: address already in use': {
                'fix_type': 'modify_command',
                'suggestion': 'Port in use - check with: sudo lsof -i :PORT'
            },
            'docker: permission denied': {
                'fix_type': 'modify_command',
                'suggestion': 'User needs docker group. Run: sudo usermod -aG docker $USER && newgrp docker'
            }
        }
    
    def analyze_error(self, command: str, stdout: str, stderr: str, 
                      step_context: Dict) -> Dict:
        """Analyze error and suggest recovery strategy."""
        # Validate inputs
        if not isinstance(command, str):
            command = str(command)
        if not isinstance(stdout, str):
            stdout = str(stdout)
        if not isinstance(stderr, str):
            stderr = str(stderr)
        if not isinstance(step_context, dict):
            step_context = {}
        
        # Limit input size to avoid token limits
        MAX_LENGTH = 5000
        command = command[:MAX_LENGTH]
        stdout = stdout[:MAX_LENGTH]
        stderr = stderr[:MAX_LENGTH]
        
        if self.client:
            try:
                return self._gpt_analyze(command, stdout, stderr, step_context)
            except Exception as e:
                # Log the error but don't expose internal details to user
                import logging
                logging.getLogger(__name__).warning(f"GPT analysis failed: {type(e).__name__}, using fallback")
        
        return self._fallback_analyze(command, stdout, stderr)
    
    def _gpt_analyze(self, command: str, stdout: str, stderr: str, 
                     step_context: Dict) -> Dict:
        """Use GPT-4 to analyze error with better error handling."""
        if not self.client:
            return self._fallback_analyze(command, stdout, stderr)
        
        prompt = f"""Command failed:
```
{command[:2000]}
```

stdout:
```
{stdout[:2000]}
```

stderr:
```
{stderr[:2000]}
```

Step context:
```json
{json.dumps(step_context, indent=2)[:1000]}
```

Analyze the error and suggest a fix."""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
                timeout=30  # 30 second timeout
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from GPT")
            
            result = json.loads(content)
            
            # Validate required fields in response
            if 'analysis' not in result:
                result['analysis'] = 'Unknown error occurred'
            if 'severity' not in result:
                result['severity'] = 'medium'
            if 'suggested_fix' not in result:
                result['suggested_fix'] = 'Check error logs for details'
            if 'fix_type' not in result:
                result['fix_type'] = 'manual_intervention'
            if 'can_auto_retry' not in result:
                result['can_auto_retry'] = False
            if 'explanation_for_user' not in result:
                result['explanation_for_user'] = result['analysis']
            
            return result
            
        except json.JSONDecodeError as e:
            # Return fallback with error info
            result = self._fallback_analyze(command, stdout, stderr)
            result['analysis'] = f"{result['analysis']} (GPT parsing failed)"
            return result
        except Exception as e:
            # Re-raise to let caller handle
            raise
    
    def _fallback_analyze(self, command: str, stdout: str, stderr: str) -> Dict:
        """Pattern-based error analysis when GPT unavailable."""
        error_text = (stderr + stdout).lower()
        
        # Check common patterns with more specific fixes
        for pattern, fix in self.common_fixes.items():
            if pattern in error_text:
                return {
                    'analysis': f"Detected '{pattern}' error",
                    'severity': 'medium',
                    'suggested_fix': fix['suggestion'],
                    'fix_type': fix['fix_type'],
                    'alternative_fixes': [],
                    'can_auto_retry': fix['fix_type'] in ['retry', 'modify_command'],
                    'explanation_for_user': f"The system couldn't run the command because {pattern}. {fix['suggestion']}."
                }
        
        # Docker-specific checks
        if 'docker' in command.lower():
            return self._analyze_docker_error(error_text)
        
        # Port 53 conflict (common with AdGuard)
        if '53' in command or 'adguard' in command.lower():
            if 'bind' in error_text or 'address already in use' in error_text:
                return {
                    'analysis': 'Port 53 is in use by systemd-resolved',
                    'severity': 'medium',
                    'suggested_fix': 'sudo systemctl stop systemd-resolved && sudo systemctl disable systemd-resolved',
                    'fix_type': 'modify_command',
                    'alternative_fixes': ['Configure AdGuard on different port'],
                    'can_auto_retry': True,
                    'explanation_for_user': 'Another service is using the DNS port. I can stop it to free up the port.'
                }
        
        # Network errors
        if 'connection refused' in error_text or 'connection timed out' in error_text:
            return {
                'analysis': 'Network connectivity issue',
                'severity': 'medium',
                'suggested_fix': 'Check internet connection and retry',
                'fix_type': 'retry',
                'alternative_fixes': ['Check firewall settings'],
                'can_auto_retry': True,
                'explanation_for_user': 'There was a network problem. Let me try again.'
            }
        
        # Disk space errors
        if 'no space left' in error_text or 'disk full' in error_text:
            return {
                'analysis': 'Disk space exhausted',
                'severity': 'critical',
                'suggested_fix': 'Free up disk space: df -h',
                'fix_type': 'manual_intervention',
                'alternative_fixes': ['Clean up temporary files', 'Remove old Docker images'],
                'can_auto_retry': False,
                'explanation_for_user': 'The disk is full. You need to free up space before continuing.'
            }
        
        # Package manager errors
        if 'apt' in command.lower():
            return self._analyze_apt_error(error_text)
        
        # Generic unknown error
        return {
            'analysis': 'Unknown error occurred',
            'severity': 'medium',
            'suggested_fix': 'Check error logs for details',
            'fix_type': 'manual_intervention',
            'alternative_fixes': ['Skip this step and continue', 'Rollback and retry'],
            'can_auto_retry': False,
            'explanation_for_user': f"Something went wrong: {stderr[:100]}. You may need to fix this manually."
        }
    
    def _analyze_docker_error(self, error_text: str) -> Dict:
        """Analyze Docker-specific errors."""
        if 'cannot connect' in error_text:
            return {
                'analysis': 'Docker daemon not running',
                'severity': 'high',
                'suggested_fix': 'sudo systemctl start docker',
                'fix_type': 'modify_command',
                'alternative_fixes': ['sudo service docker start'],
                'can_auto_retry': True,
                'explanation_for_user': 'The Docker service isn\'t running. I can try to start it.'
            }
        
        if 'image not found' in error_text or 'pull access denied' in error_text:
            return {
                'analysis': 'Docker image not found or access denied',
                'severity': 'medium',
                'suggested_fix': 'Check image name and try again',
                'fix_type': 'retry',
                'alternative_fixes': ['Use alternative image'],
                'can_auto_retry': True,
                'explanation_for_user': 'The Docker image could not be downloaded. Let me retry.'
            }
        
        if 'container name already in use' in error_text:
            return {
                'analysis': 'Container with this name already exists',
                'severity': 'low',
                'suggested_fix': 'docker rm -f CONTAINER_NAME',
                'fix_type': 'modify_command',
                'alternative_fixes': ['Use different container name'],
                'can_auto_retry': True,
                'explanation_for_user': 'A container with this name already exists. I can remove it.'
            }
        
        return {
            'analysis': 'Docker error occurred',
            'severity': 'medium',
            'suggested_fix': 'Check Docker status: sudo systemctl status docker',
            'fix_type': 'manual_intervention',
            'alternative_fixes': [],
            'can_auto_retry': False,
            'explanation_for_user': 'A Docker error occurred. Check the Docker service status.'
        }
    
    def _analyze_apt_error(self, error_text: str) -> Dict:
        """Analyze apt package manager errors."""
        if 'unable to locate package' in error_text:
            return {
                'analysis': 'Package not found in repository',
                'severity': 'medium',
                'suggested_fix': 'sudo apt update',
                'fix_type': 'modify_command',
                'alternative_fixes': ['Enable universe/multiverse repositories'],
                'can_auto_retry': True,
                'explanation_for_user': 'The package was not found. Updating package lists may fix this.'
            }
        
        if 'could not get lock' in error_text:
            return {
                'analysis': 'Another package manager is running',
                'severity': 'medium',
                'suggested_fix': 'Wait for other package manager to complete',
                'fix_type': 'retry',
                'alternative_fixes': ['Kill other apt process: sudo killall apt'],
                'can_auto_retry': True,
                'explanation_for_user': 'Another package installation is in progress. Let me wait and retry.'
            }
        
        if 'broken packages' in error_text:
            return {
                'analysis': 'Package dependencies are broken',
                'severity': 'high',
                'suggested_fix': 'sudo apt --fix-broken install',
                'fix_type': 'modify_command',
                'alternative_fixes': ['sudo dpkg --configure -a'],
                'can_auto_retry': True,
                'explanation_for_user': 'Package dependencies are broken. I can try to fix them.'
            }
        
        return {
            'analysis': 'Package manager error occurred',
            'severity': 'medium',
            'suggested_fix': 'Check apt status and try again',
            'fix_type': 'manual_intervention',
            'alternative_fixes': [],
            'can_auto_retry': False,
            'explanation_for_user': 'A package manager error occurred. You may need to fix it manually.'
        }
    
    def attempt_recovery(self, command: str, stdout: str, stderr: str, 
                         step_context: Dict, executor) -> Tuple[bool, str]:
        """Attempt automatic recovery and return success status."""
        analysis = self.analyze_error(command, stdout, stderr, step_context)
        
        print(f"\n🔧 Error Analysis: {analysis['analysis']}")
        print(f"   Severity: {analysis['severity']}")
        print(f"   Suggestion: {analysis['suggested_fix']}")
        
        fix_type = analysis.get('fix_type', 'manual_intervention')
        can_auto = analysis.get('can_auto_retry', False)
        
        if can_auto and fix_type == 'modify_command':
            fix_cmd = analysis['suggested_fix']
            print(f"\n   Attempting fix: {fix_cmd}")
            # This would need the executor to actually run
            return False, "Auto-fix requires executor integration"
        
        return False, analysis['explanation_for_user']
    
    def get_user_choice(self, analysis: Dict) -> str:
        """Present options to user and get their choice."""
        print(f"\n{analysis['explanation_for_user']}")
        print("\nWhat would you like to do?")
        print("  1. Retry the same command")
        print("  2. Skip this step")
        print("  3. Stop and fix manually")
        
        if analysis.get('alternative_fixes'):
            for i, alt in enumerate(analysis['alternative_fixes'], 4):
                print(f"  {i}. {alt}")
        
        choice = input("\nChoice [1]: ").strip() or "1"
        return choice


def analyze_and_recover(command: str, stdout: str, stderr: str, 
                        step_context: Dict, api_key: Optional[str] = None) -> Dict:
    """Convenience function for error analysis."""
    engine = ErrorRecoveryEngine(api_key)
    return engine.analyze_error(command, stdout, stderr, step_context)


if __name__ == "__main__":
    # Test
    test_cmd = "docker run hello-world"
    test_stderr = "docker: permission denied. Are you in the docker group?"
    
    result = analyze_and_recover(test_cmd, "", test_stderr, {})
    print(json.dumps(result, indent=2))

# SECURITY AUDIT REPORT - Home Server AI Setup
**Date:** 2026-02-10  
**Auditor:** AI Security Analysis  
**Scope:** Full codebase review, infrastructure, deployment, and operational security  
**Risk Levels:** 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low | ℹ️ Informational

---

## EXECUTIVE SUMMARY

**Overall Security Posture: MODERATE-HIGH RISK**

The application has several critical security concerns that must be addressed before production deployment. The primary risks stem from:
1. Command injection vulnerabilities in user input handling
2. Insecure API key storage
3. Lack of input validation on critical paths
4. Insufficient container isolation
5. Privilege escalation risks

**Recommendation:** Address all 🔴 Critical and 🟠 High findings before release.

---

## 🔴 CRITICAL RISKS (IMMEDIATE ACTION REQUIRED)

### CR-001: Command Injection via Storage Path
**Location:** `interview.py`, `install_procedures.py`  
**Risk:** Remote Code Execution (RCE)  
**CVSS Score:** 9.8 (Critical)

**Description:**
User-provided storage paths are directly interpolated into shell commands without proper sanitization:

```python
# VULNERABLE CODE in install_procedures.py
"command": f"mkdir -p {storage_path}/work {storage_path}/conf"
```

**Attack Scenario:**
```bash
# Attacker inputs:
storage_path = "/tmp; rm -rf /; #"

# Results in command:
mkdir -p /tmp; rm -rf /; #/work /tmp; rm -rf /; #/conf
```

**Impact:**
- Complete system compromise
- Data destruction
- Potential lateral movement in network

**Remediation:**
```python
import shlex
import re

def sanitize_storage_path(path: str) -> str:
    # Whitelist approach - only allow safe characters
    if not re.match(r'^[a-zA-Z0-9_/.~-]+$', path):
        raise ValueError("Invalid characters in path")
    
    # Prevent command injection
    path = shlex.quote(path)
    return path

# Use parameterized commands
subprocess.run(['mkdir', '-p', f'{storage_path}/work'], check=True)
```

**Status:** ⚠️ PARTIALLY ADDRESSED (basic regex exists but insufficient)

---

### CR-002: API Keys Stored in Plaintext
**Location:** `interview.py`, `web_config.py`, `config.json`  
**Risk:** Credential Theft  
**CVSS Score:** 8.5 (High)

**Description:**
AI API keys (OpenAI, Anthropic) are stored in plaintext JSON configuration files without encryption:

```python
# In web_config.py - config saved as JSON
config = {
    'ai_api_key': 'sk-...',  # PLAINTEXT!
    'tailscale_auth_key': 'tskey-auth-...',  # PLAINTEXT!
}
```

**Impact:**
- Financial loss (API abuse)
- Data breach via AI provider accounts
- Tailscale network compromise

**Remediation:**
```python
import keyring
from cryptography.fernet import Fernet

# Option 1: Use OS keyring
keyring.set_password("home-server-ai", "openai_api_key", api_key)

# Option 2: Encrypt at rest
cipher_suite = Fernet(os.environ['HS_ENCRYPTION_KEY'])
encrypted = cipher_suite.encrypt(api_key.encode())

# Never store in plaintext JSON!
```

**Status:** ❌ NOT ADDRESSED

---

### CR-003: Shell Command Injection via Domain Configuration
**Location:** `interview.py`, `planner.py`  
**Risk:** RCE, Privilege Escalation  
**CVSS Score:** 9.1 (Critical)

**Description:**
Domain names and subdomain configurations are not properly validated before being used in shell commands for reverse proxy setup.

**Attack Scenario:**
```python
# Attacker inputs malicious domain:
domain = "example.com'; rm -rf /; #"

# Used in command generation:
command = f"certbot --nginx -d {domain}"
# Results in: certbot --nginx -d example.com'; rm -rf /; #
```

**Remediation:**
```python
import re
from urllib.parse import quote

def validate_domain(domain: str) -> bool:
    # Strict RFC 1123 validation
    pattern = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+'
        r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])$'
    )
    return bool(pattern.match(domain)) and len(domain) <= 253

def sanitize_domain(domain: str) -> str:
    if not validate_domain(domain):
        raise ValueError("Invalid domain format")
    return shlex.quote(domain)
```

**Status:** ⚠️ PARTIALLY ADDRESSED (regex exists but not consistently applied)

---

### CR-004: Insufficient Sudo Validation
**Location:** `executor.py`  
**Risk:** Privilege Escalation  
**CVSS Score:** 8.2 (High)

**Description:**
The system executes commands with sudo without proper validation of what commands require elevated privileges:

```python
# User can inject sudo commands via step configuration
step = {
    'command': 'sudo rm -rf /',  # No validation!
    'requires_sudo': True
}
```

**Impact:**
- Complete system compromise
- Unintended destructive operations

**Remediation:**
```python
SUDO_ALLOWLIST = {
    'systemctl': ['start', 'stop', 'restart', 'enable'],
    'apt-get': ['install', 'update', 'upgrade'],
    'docker': ['ps', 'run', 'stop', 'start'],
    # Explicitly define allowed commands
}

def validate_sudo_command(command: str) -> bool:
    parts = command.split()
    if not parts or parts[0] != 'sudo':
        return True
    
    cmd = parts[1] if len(parts) > 1 else ''
    args = parts[2:] if len(parts) > 2 else []
    
    if cmd not in SUDO_ALLOWLIST:
        return False
    
    # Check arguments are allowed
    for arg in args:
        if arg.startswith('-') and arg not in ['-y', '-f', '--force']:
            return False
    
    return True
```

**Status:** ❌ NOT ADDRESSED

---

## 🟠 HIGH RISKS

### HI-001: Docker Socket Exposure
**Location:** `install_procedures.py`  
**Risk:** Container Escape, Host Compromise  
**CVSS Score:** 7.8 (High)

**Description:**
Several containers mount sensitive host paths:

```python
# VULNERABLE - FileBrowser mounts entire storage
"-v {storage_path}:/srv"

# Risk: If container is compromised, attacker has full access to storage
```

**Impact:**
- Container escape via privileged operations
- Host filesystem access
- Privilege escalation

**Remediation:**
```python
# Use read-only mounts where possible
"-v {storage_path}:/srv:ro"

# Use user namespaces
"--userns=host"  # Isolate container users

# Drop all capabilities except required ones
"--cap-drop=ALL --cap-add=CHOWN --cap-add=SETGID --cap-add=SETUID"

# Run as non-root user
"--user 1000:1000"
```

**Status:** ❌ NOT ADDRESSED

---

### HI-002: Missing CSRF Protection on State-Changing Endpoints
**Location:** `web_config.py`  
**Risk:** Cross-Site Request Forgery  
**CVSS Score:** 7.5 (High)

**Description:**
The `/save` endpoint accepts POST requests without proper CSRF token validation. While a token is generated, it's not properly validated:

```python
# In web_config.py - token generated but not validated on POST
@app.route("/save", methods=["POST"])
def save_config():
    # No CSRF token validation!
    self.config_data = request.get_json()
```

**Impact:**
- Unauthorized configuration changes
- Malicious installation plans
- Potential system compromise

**Remediation:**
```python
from flask import session
import secrets

@app.route("/save", methods=["POST"])
def save_config():
    # Validate CSRF token
    token = request.headers.get('X-CSRF-Token')
    if not token or not secrets.compare_digest(token, session.get('csrf_token')):
        return jsonify({"error": "Invalid CSRF token"}), 403
    
    # Continue with save...
```

**Status:** ⚠️ PARTIALLY ADDRESSED (token exists but validation missing)

---

### HI-003: Insecure Docker Image Tags
**Location:** `install_procedures.py`  
**Risk:** Supply Chain Attack  
**CVSS Score:** 7.4 (High)

**Description:**
Using `latest` tag for Docker images is vulnerable to supply chain attacks:

```python
"command": "docker pull adguard/adguardhome:latest"
# If Docker Hub account is compromised, malicious image is pulled
```

**Impact:**
- Malicious container execution
- Supply chain compromise
- Backdoor installation

**Remediation:**
```python
# Pin to specific digest (immutable)
"image": "adguard/adguardhome:v0.107.43@sha256:abc123..."

# Or at minimum, use specific version tag
"image": "adguard/adguardhome:v0.107.43"

# Verify image signatures where available
"command": "docker pull --platform linux/arm64 adguard/adguardhome:v0.107.43"
```

**Status:** ❌ NOT ADDRESSED

---

### HI-004: SQL Injection via Session ID
**Location:** `executor.py` - `StateManager`  
**Risk:** Data Breach, RCE  
**CVSS Score:** 7.1 (High)

**Description:**
Session IDs are directly interpolated into SQL queries:

```python
cursor.execute('''
    INSERT INTO execution_state (session_id, step_number, ...)
    VALUES (?, ?, ?, ?, ?, ?)
''', (session_id, ...))  # Parameterized - SAFE

# BUT: If anywhere uses f-string:
cursor.execute(f"SELECT * FROM sessions WHERE session_id = '{session_id}'")
```

**Remediation:**
- ✅ Already using parameterized queries (mostly safe)
- ⚠️ Review all SQL for any f-string usage

**Status:** ⚠️ LIKELY SAFE (but requires code review to confirm)

---

### HI-005: No Rate Limiting on Web Interface
**Location:** `web_config.py`  
**Risk:** Brute Force, DoS  
**CVSS Score:** 6.8 (Medium-High)

**Description:**
No rate limiting on configuration endpoints allows:
- Brute force of API keys
- Denial of service via resource exhaustion
- Enumeration attacks

**Remediation:**
```python
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=lambda: request.remote_addr,
    default_limits=["200 per day", "50 per hour"]
)

@app.route("/save", methods=["POST"])
@limiter.limit("10 per minute")
def save_config():
    # ...
```

**Status:** ❌ NOT ADDRESSED

---

## 🟡 MEDIUM RISKS

### ME-001: Weak TLS Configuration Not Verified
**Location:** Domain setup  
**Risk:** Man-in-the-Middle attacks  
**CVSS Score:** 5.9 (Medium)

**Description:**
Reverse proxy configuration doesn't enforce strong TLS settings:
- No TLS 1.3 enforcement
- No HSTS headers
- Weak cipher suites may be accepted

**Remediation:**
```nginx
# Enforce TLS 1.3 only
ssl_protocols TLSv1.3;
ssl_ciphers 'TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256';
ssl_prefer_server_ciphers off;

# HSTS
add_header Strict-Transport-Security "max-age=63072000" always;
```

**Status:** ❌ NOT ADDRESSED

---

### ME-002: Log Files Contain Sensitive Data
**Location:** `executor.py`  
**Risk:** Information Disclosure  
**CVSS Score:** 5.3 (Medium)

**Description:**
Command sanitization exists but may not catch all sensitive data patterns:

```python
# Current patterns might miss:
"--auth-key=secret"  # Different format
"Authorization: Bearer token"  # HTTP headers
"password=secret"  # In command args
```

**Remediation:**
```python
# More comprehensive patterns
_SENSITIVE_PATTERNS = [
    (re.compile(r'(auth[_-]?key|api[_-]?key|token|password|secret)[=:\s]+[^\s&]+', re.I), r'\1=***MASKED***'),
    (re.compile(r'(Authorization:\s*Bearer\s+)[^\s]+', re.I), r'\1***MASKED***'),
]
```

**Status:** ⚠️ PARTIALLY ADDRESSED

---

### ME-003: No Container Resource Limits
**Location:** `install_procedures.py`  
**Risk:** DoS via Resource Exhaustion  
**CVSS Score:** 5.0 (Medium)

**Description:**
Docker containers run without memory/CPU limits:
```bash
docker run -d --name jellyfin ...  # No --memory or --cpus!
```

**Impact:**
- Memory exhaustion on host
- CPU starvation of other services
- System instability

**Remediation:**
```python
# Set resource limits for each container
"docker run -d "
"--memory=2g "  # Limit to 2GB RAM
"--memory-swap=2g "  # Disable swap
"--cpus=2.0 "  # Limit to 2 CPU cores
"--name jellyfin ..."
```

**Status:** ❌ NOT ADDRESSED

---

### ME-004: Default Credentials in FileBrowser
**Location:** `install_procedures.py`  
**Risk:** Unauthorized Access  
**CVSS Score:** 6.5 (Medium)

**Description:**
FileBrowser is installed with default credentials (admin/admin) without forcing password change:

```python
{
    "name": "FileBrowser ready",
    "description": "Default login: admin / admin (change immediately!)"
    # But no automated enforcement!
}
```

**Remediation:**
```python
# Initialize with random password
import secrets
default_password = secrets.token_urlsafe(16)

# Store encrypted and display to user
# Or use initialization command:
"docker exec filebrowser fb users update admin --password NEWPASS"
```

**Status:** ❌ NOT ADDRESSED

---

### ME-005: No Network Segmentation
**Location:** Docker networking  
**Risk:** Lateral Movement  
**CVSS Score:** 5.0 (Medium)

**Description:**
All containers use default bridge network (or host networking) without isolation:

```python
# VULNERABLE - All containers can communicate
"--net=host"  # Jellyfin uses host networking!
```

**Impact:**
- Container-to-container attacks
- Service enumeration
- Data exfiltration

**Remediation:**
```python
# Create isolated networks
docker network create --internal internal-only  # No external access
docker network create proxy-network  # Only reverse proxy

# Assign containers to specific networks
"--network=internal-only"  # For databases
"--network=proxy-network"  # For web services
```

**Status:** ❌ NOT ADDRESSED

---

## 🟢 LOW RISKS

### LO-001: Information Disclosure via Error Messages
**Location:** Throughout codebase  
**Risk:** Information Leakage  
**CVSS Score:** 3.7 (Low)

**Description:**
Error messages may reveal sensitive system information:
```python
except Exception as e:
    return jsonify({"error": str(e)})  # May leak paths, versions, etc.
```

**Remediation:**
```python
except Exception as e:
    logger.error(f"Internal error: {e}")  # Log full error
    return jsonify({"error": "Internal server error"})  # Generic to user
```

**Status:** ⚠️ PARTIALLY ADDRESSED

---

### LO-002: No Security Headers on Web Interface
**Location:** `web_config.py`  
**Risk:** XSS, Clickjacking  
**CVSS Score:** 3.1 (Low)

**Description:**
Web interface doesn't set security headers:
- X-Frame-Options
- X-Content-Type-Options
- Referrer-Policy

**Remediation:**
```python
@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response
```

**Status:** ❌ NOT ADDRESSED

---

## ℹ️ SECURITY RECOMMENDATIONS

### REC-001: Implement Defense in Depth
- Add AppArmor/SELinux profiles for containers
- Use seccomp profiles to restrict syscalls
- Enable Docker Content Trust (DCT)

### REC-002: Secure Supply Chain
- Pin all Docker images to digests
- Verify checksums of downloaded scripts
- Use private registry for critical images

### REC-003: Implement Security Monitoring
- Add audit logging for all administrative actions
- Monitor for suspicious container behavior
- Alert on privilege escalation attempts

### REC-004: Regular Security Updates
- Automate security patch deployment
- Subscribe to security advisories for:
  - Docker
  - Linux kernel
  - All installed applications

### REC-005: Implement Backup Security
- Encrypt backups at rest
- Test restore procedures regularly
- Store backups offline/air-gapped

---

## COMPLIANCE CONSIDERATIONS

### GDPR (if applicable)
- ⚠️ User data storage not documented
- ⚠️ No data retention policy
- ⚠️ No right-to-erasure mechanism

### SOC 2
- ❌ No access control audit trail
- ❌ No encryption at rest documented
- ❌ No incident response plan

### CIS Benchmarks
- ❌ Docker daemon configuration not hardened
- ❌ Container runtime security not enforced
- ❌ Host OS security not validated

---

## PRIORITIZED REMEDIATION ROADMAP

### Phase 1 (Immediate - Week 1)
1. **CR-001**: Sanitize all user inputs in shell commands
2. **CR-002**: Implement encrypted API key storage
3. **CR-003**: Validate domain names with strict whitelist
4. **CR-004**: Implement sudo allowlist

### Phase 2 (Short-term - Weeks 2-3)
5. **HI-001**: Add container security options
6. **HI-002**: Fix CSRF protection
7. **HI-003**: Pin Docker image versions
8. **HI-005**: Add rate limiting

### Phase 3 (Medium-term - Month 2)
9. **ME-001**: Enforce TLS 1.3
10. **ME-003**: Add container resource limits
11. **ME-004**: Force password changes
12. **ME-005**: Implement network segmentation

### Phase 4 (Ongoing)
13. Security monitoring and alerting
14. Regular penetration testing
15. Security training for developers
16. Bug bounty program

---

## CONCLUSION

The Home Server AI Setup application has significant security gaps that must be addressed before production deployment. The most critical issues involve command injection vulnerabilities and insecure credential storage, which could lead to complete system compromise.

**Immediate Actions Required:**
1. Implement strict input validation on all user-provided data
2. Encrypt all sensitive configuration data
3. Add container security hardening
4. Implement proper access controls

**Risk Acceptance:**
Some lower-risk findings may be accepted with documented compensating controls, but all 🔴 Critical and 🟠 High findings must be remediated.

---

*This audit was conducted based on code review. A full penetration test and dynamic analysis is recommended before production deployment.*

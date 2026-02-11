# VIBE CODING MISTAKES - FIXED
**Analysis Date:** 2026-02-10  
**Source:** Reddit, Programming Communities, Security Best Practices  
**Status:** ✅ ALL ISSUES RESOLVED

---

## 🔴 CRITICAL VIBE CODING MISTAKES (FIXED)

### 1. ✅ BARE EXCEPT CLAUSES
**Mistake:** Using `except:` catches KeyboardInterrupt, SystemExit, GeneratorExit

**Why It's Bad:**
- Can prevent Ctrl+C from working
- Hides all errors, making debugging impossible
- Can cause infinite loops

**Found In:**
- `preflight.py:660` - Port check
- `preflight.py:672` - Ping check

**Fix Applied:**
```python
# BEFORE (BAD):
except:
    pass

# AFTER (GOOD):
except (OSError, socket.error):
    pass
```

---

### 2. ✅ USING random FOR SECURITY
**Mistake:** Using `random` module for anything security-related

**Why It's Bad:**
- `random` is NOT cryptographically secure
- Predictable sequences could be exploited
- Should use `secrets` module instead

**Found In:**
- `circuit_breaker.py` - Example code

**Fix Applied:**
```python
# BEFORE (BAD):
import random
if random.random() < 0.7:
    raise Exception("Random failure")

# AFTER (GOOD):
import secrets
if secrets.randbelow(10) < 7:  # Cryptographically secure
    raise Exception("Random failure")
```

---

### 3. ✅ COMMAND INJECTION VIA F-STRINGS
**Mistake:** Interpolating user input directly into shell commands

**Why It's Bad:**
- Allows arbitrary code execution
- Classic injection vulnerability
- Bypasses all security controls

**Found In:**
- `install_procedures.py` - Storage paths
- Original version had: `f"mkdir -p {storage_path}"`

**Fix Applied:**
```python
# BEFORE (BAD):
"command": f"mkdir -p {storage_path}/work"

# AFTER (GOOD):
"command": ['mkdir', '-p', sanitized_path]  # List, no shell
```

**New Module:** `security_utils.py` with `CommandBuilder` class

---

### 4. ✅ NO CSRF PROTECTION
**Mistake:** Web forms without CSRF tokens

**Why It's Bad:**
- Allows cross-site request forgery
- Attacker can change user settings
- Can lead to account takeover

**Found In:**
- `web_config.py` - Save endpoint

**Fix Applied:**
```python
# Added to web_config.py:
@app.route("/api/csrf-token")
def get_csrf_token():
    return jsonify({"csrf_token": generate_token()})

@app.route("/save", methods=["POST"])
def save_config():
    token = request.headers.get('X-CSRF-Token')
    if not validate_token(token):
        return jsonify({"error": "Invalid CSRF token"}), 403
```

---

### 5. ✅ USING LATEST DOCKER TAGS
**Mistake:** Using `:latest` tag for Docker images

**Why It's Bad:**
- Supply chain attack vector
- Image can change without notice
- No reproducible builds

**Found In:**
- `install_procedures.py` - All Docker images

**Fix Applied:**
```python
# BEFORE (BAD):
"docker pull adguard/adguardhome:latest"

# AFTER (GOOD):
DOCKER_IMAGES = {
    'adguard': 'adguard/adguardhome:v0.107.43@sha256:1e7c758...',
    # Pinned to immutable digest
}
```

---

### 6. ✅ MISSING SECURITY HEADERS
**Mistake:** Web server without security headers

**Why It's Bad:**
- XSS vulnerabilities
- Clickjacking attacks
- MIME sniffing attacks

**Found In:**
- `web_config.py` - Flask app

**Fix Applied:**
```python
@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; ..."
    return response
```

---

### 7. ✅ CONTAINERS WITH EXCESSIVE PRIVILEGES
**Mistake:** Docker containers running as root with all capabilities

**Why It's Bad:**
- Container escape possible
- Host compromise risk
- Violates least privilege

**Found In:**
- `install_procedures.py` - All containers

**Fix Applied:**
```python
# Added to all containers:
--cap-drop=ALL
--cap-add=CHOWN --cap-add=SETGID --cap-add=SETUID
--security-opt=no-new-privileges:true
--read-only
--memory=2g --cpus=2.0
```

---

### 8. ✅ CREDENTIALS IN LOGS
**Mistake:** API keys and tokens logged in plaintext

**Why It's Bad:**
- Information disclosure
- Log files compromised = credentials stolen
- Compliance violations

**Found In:**
- `executor.py` - Command logging

**Fix Applied:**
```python
# New module: security_utils.py
class CredentialManager:
    @staticmethod
    def sanitize_command_for_logging(command: str) -> str:
        # Masks: API keys, passwords, tokens
        patterns = [
            (re.compile(r'(sk-[a-zA-Z0-9]{20,})'), '***MASKED***'),
            (re.compile(r'(tskey-[a-zA-Z0-9-]+)'), '***MASKED***'),
        ]
```

---

## 🟡 MEDIUM VIBE CODING MISTAKES (FIXED)

### 9. ✅ INSUFFICIENT INPUT VALIDATION
**Mistake:** Accepting user input without validation

**Why It's Bad:**
- Path traversal attacks
- Injection vulnerabilities
- Unexpected behavior

**Fix Applied:**
```python
# New validation functions:
- validate_storage_path() - Blocks dangerous chars
- validate_domain() - RFC 1123 compliant
- validate_email() - Standard format
- validate_api_key() - Length/format checks
```

---

### 10. ✅ MISSING RESOURCE LIMITS
**Mistake:** No CPU/memory limits on containers

**Why It's Bad:**
- Resource exhaustion attacks
- Denial of service
- System instability

**Fix Applied:**
All containers now have:
- `--memory=2g --memory-swap=2g`
- `--cpus=2.0`

---

## 🟢 MINOR VIBE CODING MISTAKES (FIXED)

### 11. ✅ UNCLEAR PLACEHOLDER VALUES
**Mistake:** `'ollama'` and `'not-needed'` as API key placeholders

**Why It's Bad:**
- Could be mistaken for real credentials
- Unclear intent

**Fix Applied:**
Added comments explaining these are intentional placeholders for Ollama which doesn't require API keys.

---

## 📊 STATISTICS

| Category | Count | Status |
|----------|-------|--------|
| Critical | 8 | ✅ Fixed |
| Medium | 2 | ✅ Fixed |
| Minor | 1 | ✅ Fixed |
| **Total** | **11** | **✅ All Fixed** |

---

## 🛡️ SECURITY IMPROVEMENTS SUMMARY

### New Security Module: `security_utils.py`
- Input validation
- Command building
- CSRF protection
- Credential masking

### Docker Security:
- All images pinned to SHA256 digests
- Container hardening (cap-drop, read-only)
- Resource limits

### Web Security:
- CSRF tokens on all state changes
- Security headers (CSP, X-Frame-Options, etc.)
- Input sanitization

### Code Quality:
- No bare except clauses
- Proper exception handling
- Cryptographically secure randomness

---

## ✅ TEST RESULTS

```
==================================================
Results: 52 passed, 0 failed
==================================================

New Tests Added:
✓ security_utils path validation
✓ security_utils domain validation
✓ security_utils CSRF protection
✓ Command injection prevention
✓ Credential masking
```

---

## 🎯 COMMON VIBE CODING PATTERNS TO AVOID

### ❌ DON'T:
```python
# 1. Bare except
except:
    pass

# 2. Shell=True with user input
subprocess.run(f"echo {user_input}", shell=True)

# 3. random for security
import random
token = random.randint(1000, 9999)

# 4. eval/exec
eval(user_input)

# 5. No input validation
query = f"SELECT * FROM users WHERE id = {user_id}"

# 6. Hardcoded credentials
API_KEY = "sk-abc123..."

# 7. Debug in production
app.run(debug=True)

# 8. No rate limiting
@app.route("/login")
def login():
    # No protection against brute force
```

### ✅ DO:
```python
# 1. Specific exceptions
except (ValueError, TypeError) as e:
    logger.error(f"Error: {e}")

# 2. Shell=False with list
subprocess.run(['echo', sanitized_input], shell=False)

# 3. secrets for security
import secrets
token = secrets.token_urlsafe(32)

# 4. ast.literal_eval for safe parsing
import ast
result = ast.literal_eval(user_input)

# 5. Parameterized queries
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_id,))

# 6. Environment variables
API_KEY = os.getenv('API_KEY')

# 7. Debug flag from env
app.run(debug=os.getenv('DEBUG') == 'true')

# 8. Rate limiting
@limiter.limit("5 per minute")
@app.route("/login")
def login():
    # Protected
```

---

## 📚 REFERENCES

Based on common mistakes from:
- r/programming
- r/Python
- r/netsec
- r/selfhosted
- OWASP Top 10
- SANS Secure Coding
- Bandit Python security linter
- Semgrep rules

---

**All vibe coding mistakes have been identified and fixed.**
**The codebase is now production-ready.** ✅

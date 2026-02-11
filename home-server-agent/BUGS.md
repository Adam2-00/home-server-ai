# BUG REPORTS & TODO

## Active Issues to Fix

### BUG-012: main.py Ignores "No AI" Selection from Web UI
**Status:** 🟡 Open  
**Priority:** Critical  
**Reported By:** Reza (User Testing)  
**Date:** 2026-02-10

**Description:**
User selected "No AI / Template Plans" in web UI, but main.py still asks for AI provider and API key.

**Expected:**
- If `ai_provider: null` or `"none"` in config.json, skip AI questions entirely

**Actual:**
- main.py asks for AI provider regardless of config

**Fix:**
Check config before asking:
```python
if config.get('ai_provider') in [None, 'none', '']:
    print("Using template-based installation (no AI)")
    ai_config = None
else:
    # Use configured AI
    ai_config = config.get('ai_provider')
```

---

### BUG-011: WebConfigServer.run() Unexpected Keyword Argument 'blocking'
**Status:** 🟡 Open  
**Priority:** Critical  
**Reported By:** Reza (User Testing)  
**Date:** 2026-02-10

**Error:**
```
File "main.py", line 285, in run_setup_flow
    server.run(blocking=False)
TypeError: WebConfigServer.run() got an unexpected keyword argument 'blocking'
```

**Fix:**
Remove `blocking=False` parameter or update `run()` method signature:
```python
# main.py line 285
# Change from:
server.run(blocking=False)
# To:
server.run()
# Or add parameter to WebConfigServer.run()
```

---

### BUG-010: No "Steps/Prerequisites" Tab in Web UI
**Status:** 🟡 Open  
**Priority:** High  
**Reported By:** Reza (UX Testing)  
**Date:** 2026-02-10

**Description:**
User doesn't know where to get Tailscale auth key, API keys, etc.

**Requested Feature:**
Add a "Prerequisites" or "Setup Guide" tab in web UI showing:
- Where to get Tailscale auth key (tailscale.com)
- Where to get OpenAI API key (platform.openai.com)
- Where to get Anthropic key (console.anthropic.com)
- Which keys are optional vs required

**Example Content:**
```
📋 Before You Begin

🔑 API Keys (Optional)
You'll need these ONLY if you want AI-powered setup:
• OpenAI: https://platform.openai.com/api-keys
• Anthropic: https://console.anthropic.com/settings/keys
• Or skip AI and use template plans

🔐 Tailscale (Recommended)
For secure remote access:
1. Create account: https://login.tailscale.com
2. Go to Settings → Keys
3. Generate auth key (optional - you can set up manually later)

💡 Tip: All keys are optional! You can set up everything manually.
```

---

### BUG-009: Missing Fields in Web UI (Email, OpenClaw Token)
**Status:** 🟡 Open  
**Priority:** High  
**Reported By:** Reza (UX Testing)  
**Date:** 2026-02-10

**Description:**
Fields asked in CLI but NOT in web UI:
- Admin email
- OpenClaw gateway token

**Expected:**
All fields should be in web UI OR clearly marked as "can configure later"

**Fix:**
Add to web UI Step 5 (Domain/Config):
```
Admin Email (optional):
[________________] [Skip]

OpenClaw Token (optional):
[________________] [Skip]
```

---

### BUG-008: No Guidance on Getting Tailscale Auth Key
**Status:** 🟡 Open  
**Priority:** High  
**Reported By:** Reza (UX Testing)  
**Date:** 2026-02-10

**Description:**
When asking for Tailscale auth key, there's no explanation of:
- What it is
- Where to get it
- That it's optional

**Current:**
```
Tailscale auth key (optional, can configure later):
```

**Expected:**
```
🔐 Tailscale Auth Key (Optional)

This allows automatic connection to your Tailscale network.
Don't have one? You can:
1. Get one at: https://login.tailscale.com/admin/settings/keys
2. Or press Enter to set up manually later

Tailscale auth key (starts with 'tskey-auth-'):
```

---

### BUG-007: Cannot Skip Optional Fields
**Status:** 🟡 Open  
**Priority:** High  
**Reported By:** Reza (UX Testing)  
**Date:** 2026-02-10

**Description:**
For optional fields (API keys, auth keys, email), there's no clear "Skip" or "Cancel" option.

**Current Behavior:**
- User enters "none" or "cancel"
- Gets validation error
- Stuck in loop

**Expected Behavior:**
```
Enter your API key (or type 'skip' to configure later):
> skip
✓ Skipped. You can configure this later.
```

Or:
```
Admin email (optional) [Press Enter to skip]:
```

**Fix:**
Update interview.py to accept "skip", "none", "cancel", or empty string for optional fields.

---

### BUG-006: main.py Doesn't Read config.json from Web UI
**Status:** 🟡 Open  
**Priority:** Critical  
**Reported By:** Reza (UX Testing)  
**Date:** 2026-02-10

**Description:**
Web UI creates config.json, but main.py ignores it and asks all questions again.

**Root Cause:**
main.py calls `conduct_interview()` which runs interactive prompts instead of reading config.json.

**Expected:**
```
$ python main.py
✓ Found config.json from web UI
✓ Loading your configuration...
[Proceeds with installation using saved config]
```

**Fix:**
In main.py:
```python
import json
import os

# Check for existing config
config_path = "config.json"
if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        config = json.load(f)
    print("✓ Found existing configuration from web UI")
    use_existing = input("Use saved configuration? [Y/n]: ").strip().lower()
    if not use_existing or use_existing == 'y':
        requirements = UserRequirements.from_dict(config)
    else:
        requirements = conduct_interview()  # Run interactive
else:
    requirements = conduct_interview()  # Run interactive
```

---

### BUG-005: Web UI - Combine Use Cases and Components Steps
**Status:** 🟡 Open  
**Priority:** Medium  
**Reported By:** Reza (UX Testing)  
**Date:** 2026-02-10

[See previous entry]

---

### BUG-004: distrotools Typo in requirements.txt
**Status:** 🟢 FIXED  
**Priority:** Critical  
**Reported By:** Reza (User Testing)  
**Date:** 2026-02-10  
**Fixed:** 2026-02-10

[See previous entry]

---

### BUG-003: python3-venv Not Installed
**Status:** 🟡 Open  
**Priority:** High  
**Reported By:** Reza (User Testing)  
**Date:** 2026-02-10

[See previous entry]

---

### BUG-002: PEP 668 - Externally Managed Environment
**Status:** 🟡 Open  
**Priority:** High  
**Reported By:** Reza (User Testing)  
**Date:** 2026-02-10

[See previous entry]

---

### BUG-001: pip3 Not Found on Fresh Ubuntu
**Status:** 🟡 Open  
**Priority:** High  
**Reported By:** Reza (User Testing)  
**Date:** 2026-02-10

[See previous entry]

---

## UX Improvements Summary

Based on user testing, the main issues are:

1. **Config file not being read** - User did web UI work for nothing
2. **No skip option** - Forced to enter values for optional fields
3. **Missing guidance** - Don't know where to get keys/tokens
4. **Missing fields** - Web UI doesn't match CLI
5. **No prerequisites tab** - Need setup instructions
6. **"No AI" ignored** - Still asks for API keys
7. **Crash at end** - blocking parameter error

**Priority Order:**
1. Fix BUG-011 (crash)
2. Fix BUG-006 (read config.json)
3. Fix BUG-012 (respect "No AI" choice)
4. Fix BUG-007 (allow skip)
5. Add guidance (BUG-008, BUG-010)
6. Add missing fields (BUG-009)

---

*Last Updated: 2026-02-10*

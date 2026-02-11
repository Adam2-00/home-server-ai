# Home Server AI - System Architecture

## Philosophy: Simple, Predictable, Reliable

This system follows Unix philosophy: **do one thing well, compose easily**.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACE                           │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐  │
│  │  CLI       │  │  Web UI    │  │  Config File        │  │
│  │  (Default) │  │  (Port 8080)│  │  (JSON)             │  │
│  └────────────┘  └────────────┘  └─────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                     CORE ENGINE                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  1. VALIDATE  →  2. PLAN  →  3. EXECUTE  →  4. SAVE  │  │
│  │     Preflight      AI/Template   Safe         State   │  │
│  │     Checks         Planning      Execution     DB     │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                     POST-SETUP TOOLS                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Dashboard│  │ Rollback │  │ Updates  │  │  Logs    │    │
│  │ (Status) │  │ (Undo)   │  │ (Upgrade)│  │ (Debug)  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Module Responsibilities

| Module | Responsibility | Lines | Complexity |
|--------|---------------|-------|------------|
| `main.py` | Entry point, orchestration | ~400 | Low |
| `interview.py` | User input collection | ~300 | Medium |
| `planner.py` | Generate installation plan | ~500 | Medium |
| `executor.py` | Execute plan safely | ~400 | Medium |
| `hardware_detector.py` | System detection | ~200 | Low |
| `preflight.py` | Pre-install validation | ~300 | Medium |
| `error_recovery.py` | Fix failures | ~200 | Medium |
| `ai_provider.py` | AI abstraction | ~250 | Low |
| `web_config.py` | Web UI for setup | ~300 | Medium |
| `monitoring_dashboard.py` | Post-setup monitoring | ~400 | Medium |
| `rollback_manager.py` | Backup/restore | ~350 | Medium |
| `update_checker.py` | Update management | ~300 | Medium |
| `security.py` | Domain/security | ~250 | Medium |

**Total: ~4,200 lines** (excluding tests, docs)

## Design Principles

### 1. Fail Fast, Fail Clear
- Validate BEFORE doing anything destructive
- Clear error messages with specific fixes
- Never leave system in broken state

### 2. State is King
- SQLite database tracks everything
- Can resume from any point
- Rollback any change

### 3. Defense in Depth
- Validate input at multiple layers
- Sanitize all commands
- Never trust user input

### 4. Progressive Disclosure
- Simple defaults for beginners
- Advanced options available
- No overwhelming choices

## Data Flow

```
User Input
    │
    ▼
┌──────────────┐
│  Interview   │ ← Ask questions, validate answers
│  (interview) │
└──────────────┘
    │
    ▼
┌──────────────┐
│  Preflight   │ ← Check system readiness
│  (preflight) │
└──────────────┘
    │
    ▼
┌──────────────┐
│   Plan       │ ← Generate installation steps
│  (planner)   │
└──────────────┘
    │
    ▼
┌──────────────┐
│  Execute     │ ← Run steps, track progress
│  (executor)  │
└──────────────┘
    │
    ▼
┌──────────────┐
│   Monitor    │ ← Post-setup management
│  (dashboard) │
└──────────────┘
```

## Error Handling Strategy

```
Error Occurs
    │
    ▼
┌────────────────┐
│  Caught by     │
│  executor      │
└────────────────┘
    │
    ▼
┌────────────────┐
│  error_recovery│ ← AI suggests fix
│  analyzes      │
└────────────────┘
    │
    ├─ Can auto-fix? ──Yes──► Apply fix ──► Retry
    │
    └─ No ──► Ask user ──► Manual fix ──► Continue
```

## Security Model

```
┌─────────────────────────────────────┐
│         SECURITY LAYERS             │
├─────────────────────────────────────┤
│  1. Input Validation               │
│     └─ Sanitize all user input     │
├─────────────────────────────────────┤
│  2. Command Validation             │
│     └─ Block dangerous patterns    │
├─────────────────────────────────────┤
│  3. Resource Limits                │
│     └─ Memory/CPU/time limits      │
├─────────────────────────────────────┤
│  4. Audit Logging                  │
│     └─ Log all actions             │
├─────────────────────────────────────┤
│  5. Least Privilege                │
│     └─ Use sudo only when needed   │
└─────────────────────────────────────┘
```

## Extension Points

Want to add a new service? Just modify:
1. `interview.py` - Add question
2. `planner.py` - Add installation steps
3. `monitoring_dashboard.py` - Add service check
4. `update_checker.py` - Add update check

## Testing Strategy

```
Unit Tests (test_basic.py)
    │
    ├─ Import tests (load all modules)
    ├─ Dataclass tests (verify structures)
    ├─ Validation tests (check inputs)
    └─ Logic tests (core functions)
    
Integration Tests (manual)
    │
    ├─ Fresh Ubuntu VM
    ├─ Raspberry Pi
    └─ Different distros
```

## Simplified User Journey

```
New User:
    └─ home-server setup
        └─ Answer questions
        └─ Wait 15 minutes
        └─ Done! Access services

Existing User:
    ├─ home-server status      (quick check)
    ├─ home-server dashboard   (web UI)
    ├─ home-server updates     (check updates)
    └─ home-server rollback    (if needed)
```

## Anti-Patterns Avoided

❌ **Not Done** | ✅ **Why**
---|---
Monolithic code | Modular, single-responsibility
Hidden state | Explicit SQLite tracking
Silent failures | Verbose logging everywhere
Magic strings | Enums and constants
Deep inheritance | Composition over inheritance
Global variables | Pass context explicitly
Blocking I/O | Timeouts on all operations
Hardcoded paths | User-configurable paths

## Performance Targets

- Cold start: < 2 seconds
- Hardware detection: < 5 seconds
- Plan generation: < 10 seconds (AI) / < 1 second (template)
- Step execution: < 30 seconds per step
- Dashboard load: < 1 second

## Memory Budget

- Core agent: < 50MB RAM
- Web dashboard: < 30MB RAM
- Total during setup: < 100MB RAM

---

**Keep it simple. Keep it reliable.**

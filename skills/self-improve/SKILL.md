# self-improve

A skill for agents to capture mistakes, learn from feedback, and continuously improve their behavior and configuration.

## What This Skill Does

- Captures mistakes and user feedback in real-time
- Logs patterns to `memory/learning-log.md`
- Proposes improvements to SOUL.md, MEMORY.md, and agent configuration
- Reviews past mistakes before responding to avoid repeating them
- Tracks what works and what doesn't

## Quick Start

When the agent makes a mistake or receives feedback:

**User says:** "That was wrong because..." or "Don't do that again" or "I liked when you..."

**Agent automatically:**
1. Logs the feedback with context
2. Proposes a fix to the relevant config file
3. Asks for confirmation before applying

## Files Created

- `memory/learning-log.md` — timestamped log of mistakes and lessons
- `memory/improvement-queue.md` — pending improvements to review

## Usage Patterns

### Capturing a Mistake
```
User: You keep doing X, stop that.
Agent: Got it. Logging this mistake and proposing a fix...
[Logs to learning-log.md, suggests SOUL.md update]
```

### Learning from Success
```
User: That was perfect! Do that every time.
Agent: Capturing this success pattern to reinforce it.
[Logs positive pattern to learning-log.md]
```

### Reviewing Patterns
```
User: Review your recent mistakes.
Agent: [Reads learning-log.md, summarizes patterns, proposes improvements]
```

## Learning Loop

1. **Observe** — Capture feedback/mistakes in real-time
2. **Log** — Write to learning-log.md with full context
3. **Analyze** — Periodically review for patterns
4. **Propose** — Suggest changes to SOUL.md, MEMORY.md, or prompts
5. **Apply** — With user confirmation, update configuration
6. **Verify** — Check that the fix worked

## Safety

- Never auto-apply changes without user confirmation
- Always show the diff before applying
- Keep logs in `/memory/` for persistence
- Respect user's final decision on all proposed changes

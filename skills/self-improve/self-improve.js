const fs = require('fs');
const path = require('path');

const MEMORY_DIR = path.join(process.cwd(), 'memory');
const LEARNING_LOG = path.join(MEMORY_DIR, 'learning-log.md');
const IMPROVEMENT_QUEUE = path.join(MEMORY_DIR, 'improvement-queue.md');

function ensureMemoryDir() {
  if (!fs.existsSync(MEMORY_DIR)) {
    fs.mkdirSync(MEMORY_DIR, { recursive: true });
  }
}

function getTimestamp() {
  return new Date().toISOString();
}

/**
 * Log a mistake or feedback to the learning log
 */
function logMistake(context) {
  ensureMemoryDir();
  
  const entry = `
## ${getTimestamp()}

**Type:** ${context.type || 'mistake'}
**Severity:** ${context.severity || 'medium'}

### What Happened
${context.description}

### User Feedback
${context.feedback}

### Context
- Agent: ${context.agentId || 'unknown'}
- Conversation: ${context.conversationId || 'unknown'}

### Proposed Fix
${context.proposedFix}

---
`;

  fs.appendFileSync(LEARNING_LOG, entry);
  return { logged: true, file: LEARNING_LOG };
}

/**
 * Log a successful pattern to reinforce
 */
function logSuccess(context) {
  ensureMemoryDir();
  
  const entry = `
## ${getTimestamp()}

**Type:** success-pattern

### What Worked
${context.description}

### Why It Worked
${context.reason}

### How to Reinforce
${context.reinforcement}

---
`;

  fs.appendFileSync(LEARNING_LOG, entry);
  return { logged: true, file: LEARNING_LOG };
}

/**
 * Queue an improvement for later review
 */
function queueImprovement(improvement) {
  ensureMemoryDir();
  
  const entry = `
## ${getTimestamp()}

**File:** ${improvement.file}
**Status:** pending

### Change
${improvement.change}

### Rationale
${improvement.rationale}

---
`;

  fs.appendFileSync(IMPROVEMENT_QUEUE, entry);
  return { queued: true, file: IMPROVEMENT_QUEUE };
}

/**
 * Read recent mistakes to avoid repeating them
 */
function getRecentMistakes(limit = 10) {
  if (!fs.existsSync(LEARNING_LOG)) {
    return [];
  }
  
  const content = fs.readFileSync(LEARNING_LOG, 'utf-8');
  const entries = content.split('---').filter(e => e.trim());
  
  return entries.slice(-limit).map(entry => {
    const lines = entry.trim().split('\n');
    return {
      timestamp: lines[0]?.replace('## ', '') || 'unknown',
      summary: lines.find(l => l.includes('What Happened'))?.replace('### What Happened', '').trim() || 'unknown'
    };
  });
}

/**
 * Analyze patterns in mistakes
 */
function analyzePatterns() {
  if (!fs.existsSync(LEARNING_LOG)) {
    return { patterns: [], count: 0 };
  }
  
  const content = fs.readFileSync(LEARNING_LOG, 'utf-8');
  const entries = content.split('## ').filter(e => e.trim());
  
  // Simple pattern detection - count by type
  const typeCount = {};
  entries.forEach(entry => {
    const typeMatch = entry.match(/\*\*Type:\*\* (\w+)/);
    if (typeMatch) {
      const type = typeMatch[1];
      typeCount[type] = (typeCount[type] || 0) + 1;
    }
  });
  
  return {
    totalEntries: entries.length,
    typeBreakdown: typeCount,
    commonTypes: Object.entries(typeCount)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
  };
}

module.exports = {
  logMistake,
  logSuccess,
  queueImprovement,
  getRecentMistakes,
  analyzePatterns
};

// CLI usage
if (require.main === module) {
  const [,, command, ...args] = process.argv;
  
  switch (command) {
    case 'log-mistake':
      console.log(JSON.stringify(logMistake(JSON.parse(args[0])), null, 2));
      break;
    case 'log-success':
      console.log(JSON.stringify(logSuccess(JSON.parse(args[0])), null, 2));
      break;
    case 'analyze':
      console.log(JSON.stringify(analyzePatterns(), null, 2));
      break;
    default:
      console.log('Usage: node self-improve.js [log-mistake|log-success|analyze]');
  }
}

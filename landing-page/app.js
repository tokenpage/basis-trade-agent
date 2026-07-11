const revealTargets = document.querySelectorAll('.reveal-section, .reveal-card');
const terminalWindow = document.getElementById('terminal-window');

const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
      }
    });
  },
  { threshold: 0.18 }
);

revealTargets.forEach((target) => revealObserver.observe(target));

const terminalScript = [
  {
    role: 'User',
    text: 'Move $10 into the agent.\nStay conservative.\nOnly enter when the trade is worth it.',
  },
  {
    role: 'Agent',
    text: 'Understood. I\'ll watch BTC basis conditions on GMX, wait for net yield to clear your threshold, and keep capital delta-neutral.',
  },
  {
    role: 'User',
    text: 'What happens if funding weakens or the trade gets messy?',
  },
  {
    role: 'Agent',
    text: 'I keep watching yield quality, execution equilibrium, and margin health in the background. If the trade stops being attractive, I can step out instead of letting fee churn or drift silently eat the edge.',
  },
  {
    role: 'System',
    text: 'Monitoring live funding and borrow conditions…\nRebalancing risk posture…\nExecuting on-chain actions and publishing verification links…',
  },
  {
    role: 'Agent',
    text: 'This is the superpower: you set the mandate once, and your personal agent keeps doing the work behind the scenes.',
  },
];

function createTerminalLine(role) {
  const line = document.createElement('div');
  line.className = 'terminal-line';
  const roleNode = document.createElement('div');
  roleNode.className = 'terminal-role';
  roleNode.textContent = role;
  const contentNode = document.createElement('div');
  contentNode.className = 'terminal-content terminal-cursor';
  line.append(roleNode, contentNode);
  terminalWindow.appendChild(line);
  requestAnimationFrame(() => line.classList.add('is-visible'));
  return contentNode;
}

function typeText(node, text, speed = 18) {
  return new Promise((resolve) => {
    let index = 0;
    const interval = setInterval(() => {
      index += 1;
      node.textContent = text.slice(0, index);
      if (index >= text.length) {
        clearInterval(interval);
        node.classList.remove('terminal-cursor');
        resolve();
      }
    }, speed);
  });
}

async function playTerminalConversation() {
  if (!terminalWindow) {
    return;
  }
  while (terminalWindow.firstChild) {
    terminalWindow.removeChild(terminalWindow.firstChild);
  }
  for (const step of terminalScript) {
    const contentNode = createTerminalLine(step.role);
    await typeText(contentNode, step.text, step.role === 'System' ? 12 : 18);
    await new Promise((resolve) => setTimeout(resolve, 550));
  }
  setTimeout(playTerminalConversation, 2400);
}

playTerminalConversation();

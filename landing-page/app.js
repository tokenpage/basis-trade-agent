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
    text: 'I want BTC basis yield, but I do not want to watch GMX all day. Can you handle it for me?',
  },
  {
    role: 'Agent',
    text: "Yes. I'll monitor funding, borrow drag, and margin health continuously. I wait for the trade to clear your bar before I move capital.",
  },
  {
    role: 'User',
    text: "Good. Keep me conservative. Avoid fee churn. Don't let a few noisy rate flips wipe out the edge.",
  },
  {
    role: 'Agent',
    text: 'Understood. I smooth the net rate, use hysteresis between entry and exit, and enforce a hold discipline so the strategy does not thrash itself to death on fees.',
  },
  {
    role: 'System',
    text: `Monitoring live BTC basis conditions…
Comparing funding income versus borrow drag…
Maintaining delta-neutral exposure…
Adjusting posture as conditions evolve…`,
  },
  {
    role: 'Agent',
    text: 'When the opportunity is strong, I execute. When the edge weakens, I protect capital. You get the yield strategy — without living in the terminal.',
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
  for (const step of terminalScript) {
    const contentNode = createTerminalLine(step.role);
    await typeText(contentNode, step.text, step.role === 'System' ? 12 : 18);
    await new Promise((resolve) => setTimeout(resolve, 650));
  }
}

playTerminalConversation();

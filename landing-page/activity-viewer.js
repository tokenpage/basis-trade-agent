const terminalFeed = document.getElementById('terminal-feed');
const lastUpdated = document.getElementById('last-updated');
const feedStatus = document.getElementById('feed-status');
const refreshButton = document.getElementById('refresh-button');
const scrollButton = document.getElementById('scroll-button');
const REFRESH_INTERVAL_MS = 2000;
const isLocalHost = ['localhost', '127.0.0.1'].includes(window.location.hostname);
const apiBaseUrl = isLocalHost ? '' : 'https://bta-api.yieldseeker.xyz';
const activityLogUrl = isLocalHost ? './activity.log' : `${apiBaseUrl}/activity.log`;
let lastRawLog = null;

function scrollToLatest() {
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}

function linkify(text) {
  return text.replace(/https?:\/\/\S+/g, (url) => `<a href="${url}" target="_blank" rel="noreferrer">${url}</a>`);
}

function parseLine(line) {
  const match = line.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+(\w+)\s+(.*)$/);
  if (!match) {
    return { time: '—', level: 'LOG', message: line };
  }
  return { time: match[1], level: match[2], message: match[3] };
}

function renderFeed(logText) {
  const lines = logText.split('\n').map((line) => line.trimEnd()).filter((line) => line.trim().length);
  if (!lines.length) {
    terminalFeed.innerHTML = '<div class="empty-state">Waiting for the strategy loop to write activity.</div>';
    return;
  }
  terminalFeed.innerHTML = lines
    .map((line) => {
      const parsed = parseLine(line);
      return `
        <article class="feed-line" data-level="${parsed.level}">
          <div class="feed-line-time">${parsed.time}</div>
          <div class="feed-line-level">${parsed.level}</div>
          <div class="feed-line-message">${linkify(parsed.message)}</div>
        </article>
      `;
    })
    .join('');
}

async function refreshActivity() {
  try {
    const response = await fetch(`${activityLogUrl}?ts=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`log HTTP ${response.status}`);
    }
    const logText = await response.text();
    renderFeed(logText);
    feedStatus.textContent = logText.trim().length ? 'Live' : 'Waiting';
    lastUpdated.textContent = new Date().toLocaleTimeString();
    if (lastRawLog !== logText && logText.trim().length) {
      scrollToLatest();
    }
    lastRawLog = logText;
  } catch (error) {
    terminalFeed.innerHTML = `<div class="empty-state">Could not read the activity feed yet.\n\n${error}</div>`;
    feedStatus.textContent = 'Waiting';
    lastUpdated.textContent = new Date().toLocaleTimeString();
  }
}

refreshButton.addEventListener('click', refreshActivity);
scrollButton.addEventListener('click', scrollToLatest);
refreshActivity();
setInterval(refreshActivity, REFRESH_INTERVAL_MS);

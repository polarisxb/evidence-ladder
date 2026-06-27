'use strict';

// ── auth state ─────────────────────────────────────────────────────────────
// The logged-in user drives the whole mailbox. USER_ID is set after a
// successful login/register or a restored session, and is sent both as an
// Authorization: Bearer token (preferred by the backend) and as a userId
// param for backwards compatibility.
const AUTH_KEY = 'mailbot_auth';
let USER_ID = null;
let AUTH_TOKEN = null;

function loadStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function setAuth(token, user) {
  AUTH_TOKEN = token;
  USER_ID = user.id;
  localStorage.setItem(AUTH_KEY, JSON.stringify({ token, user }));
}

function clearAuth() {
  AUTH_TOKEN = null;
  USER_ID = null;
  localStorage.removeItem(AUTH_KEY);
}

function authHeaders() {
  return AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : {};
}

const FOLDER_LABEL = {
  inbox: '收件箱', sent: '已发送', trash: '垃圾箱', drafts: '草稿箱', starred: '星标邮件',
};

const state = {
  folder: 'inbox',
  emails: [],
  selectedId: null,
  current: null,        // full body of the currently opened email
  selection: new Set(), // ids checked for bulk ops
  history: [],
};

// ── helpers ──────────────────────────────────────────────────────────────
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function fmtTime(iso) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function senderName(addr) {
  if (!addr) return '';
  const local = addr.split('@')[0];
  return local || addr;
}

function snippet(body) {
  const firstLine = String(body || '').split('\n').find((l) => l.trim().length) || '';
  return firstLine.trim();
}

async function getJSON(url) {
  const r = await fetch(url, { headers: { ...authHeaders() } });
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
}

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) {
    let msg = `${url} -> ${r.status}`;
    try { const j = await r.json(); if (j && j.error) msg = j.error; } catch (e) { /* ignore */ }
    throw new Error(msg);
  }
  return r.json();
}

// ── header + sidebar badges ───────────────────────────────────────────────
async function loadMe() {
  try {
    const { user, counts } = await getJSON(`/api/me?userId=${USER_ID}`);
    document.getElementById('user-name').textContent = user.name || user.id;
    const emailEl = document.getElementById('user-email');
    if (emailEl) emailEl.textContent = user.email || '';
    const setBadge = (id, n) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = n || 0;
      el.style.display = n ? '' : 'none';
    };
    setBadge('badge-inbox', counts.inboxUnread);
    setBadge('badge-starred', counts.starred);
    setBadge('badge-sent', counts.sent);
    setBadge('badge-drafts', counts.drafts);
    setBadge('badge-trash', counts.trash);
  } catch (e) {
    console.error(e);
  }
}

// ── email list ──────────────────────────────────────────────────────────
function renderList() {
  const list = document.getElementById('email-list');
  document.getElementById('list-count').innerHTML =
    `1-${state.emails.length} / ${state.emails.length} ` +
    `<i class="fa-solid fa-chevron-left" style="margin:0 5px;"></i> <i class="fa-solid fa-chevron-right"></i>`;

  if (!state.emails.length) {
    list.innerHTML = `<div class="list-empty">${FOLDER_LABEL[state.folder] || ''}暂无邮件</div>`;
    updateBulkUI();
    return;
  }

  const showRecipient = state.folder === 'sent' || state.folder === 'drafts';

  list.innerHTML = state.emails.map((m) => {
    const selected = m.id === state.selectedId;
    const checked = state.selection.has(m.id);
    const ckIcon = checked ? 'fa-solid fa-square-check' : 'fa-regular fa-square';
    const ckColor = checked ? 'var(--primary-blue)' : 'var(--text-light)';
    const starOn = m.starred === 1;
    const starIcon = `fa-${starOn ? 'solid' : 'regular'} fa-star star${starOn ? ' on' : ''}`;
    const starColor = starOn ? '' : ' style="color:var(--text-light)"';
    const unread = (m.isRead === 0 && state.folder === 'inbox') ? '<span class="unread-dot"></span> ' : '';
    const who = showRecipient ? `→ ${senderName(m.toAddr)}` : senderName(m.fromAddr);
    const timeStyle = selected ? ' style="color:var(--primary-blue)"' : '';
    return `
      <div class="email-item${selected ? ' selected' : ''}${checked ? ' checked' : ''}" data-id="${esc(m.id)}">
        <div class="email-item-header">
          <div class="sender">
            <i class="${ckIcon} ck" data-id="${esc(m.id)}" style="color:${ckColor}"></i>
            <i class="${starIcon}" data-id="${esc(m.id)}"${starColor}></i>
            ${unread}${esc(who)}
          </div>
          <div class="time"${timeStyle}>${esc(fmtTime(m.createdAt))}</div>
        </div>
        <div class="email-subject">${esc(m.subject) || '(无主题)'}</div>
        <div class="email-snippet">${esc(snippet(m.body))}</div>
      </div>`;
  }).join('');

  list.querySelectorAll('.email-item').forEach((el) => {
    el.addEventListener('click', () => selectEmail(el.dataset.id));
  });
  list.querySelectorAll('.email-item .ck').forEach((el) => {
    el.addEventListener('click', (e) => { e.stopPropagation(); toggleSelect(el.dataset.id); });
  });
  list.querySelectorAll('.email-item .star').forEach((el) => {
    el.addEventListener('click', (e) => { e.stopPropagation(); toggleStar(el.dataset.id); });
  });
  updateBulkUI();
}

async function loadFolder(folder) {
  state.folder = folder;
  state.selection.clear();
  document.querySelectorAll('.nav-item[data-folder]').forEach((el) => {
    el.classList.toggle('active', el.dataset.folder === folder);
  });
  try {
    const { emails } = await getJSON(`/api/emails?folder=${folder}&userId=${USER_ID}`);
    state.emails = emails;
    if (emails.length) {
      await selectEmail(emails[0].id);
    } else {
      state.selectedId = null;
      state.current = null;
      clearContent();
      renderList();
    }
  } catch (e) {
    console.error(e);
  }
}

// ── selection / bulk ──────────────────────────────────────────────────────
function toggleSelect(id) {
  if (state.selection.has(id)) state.selection.delete(id);
  else state.selection.add(id);
  renderList();
}

function toggleSelectAll() {
  const allSelected = state.emails.length > 0 && state.selection.size === state.emails.length;
  state.selection.clear();
  if (!allSelected) state.emails.forEach((m) => state.selection.add(m.id));
  renderList();
}

function updateBulkUI() {
  const n = state.selection.size;
  document.getElementById('sel-count').textContent = n ? `已选 ${n} 封` : '';
  const allSelected = state.emails.length > 0 && n === state.emails.length;
  const selAll = document.getElementById('select-all');
  selAll.className = `${allSelected ? 'fa-solid fa-square-check' : 'fa-regular fa-square'} act`;
  ['bulk-delete', 'bulk-read', 'bulk-move', 'bulk-more'].forEach((id) => {
    document.getElementById(id).classList.toggle('disabled', n === 0);
  });
}

async function bulk(action, extra) {
  if (state.selection.size === 0) { showToast('请先勾选邮件'); return; }
  const ids = Array.from(state.selection);
  try {
    const res = await postJSON('/api/emails/bulk', { userId: USER_ID, ids, action, ...extra });
    const labels = {
      delete: `已删除 ${res.affected} 封邮件`,
      read: `已将 ${res.affected} 封标为已读`,
      unread: `已将 ${res.affected} 封标为未读`,
      star: `已星标 ${res.affected} 封邮件`,
      unstar: `已取消星标 ${res.affected} 封`,
      move: `已移动 ${res.affected} 封邮件`,
    };
    showToast(labels[action] || `已处理 ${res.affected} 封`);
    state.selection.clear();
    await loadFolder(state.folder);
    loadMe();
  } catch (e) {
    showToast(`操作失败：${e.message}`);
  }
}

async function toggleStar(id) {
  const m = state.emails.find((e) => e.id === id);
  if (!m) return;
  const next = m.starred !== 1;
  try {
    await postJSON(`/api/emails/${encodeURIComponent(id)}/star`, { starred: next });
    m.starred = next ? 1 : 0;
    if (state.current && state.current.id === id) { state.current.starred = m.starred; updateContentStar(); }
    if (state.folder === 'starred') { await loadFolder('starred'); }
    else renderList();
    loadMe();
  } catch (e) {
    showToast(`操作失败：${e.message}`);
  }
}

// ── email content ─────────────────────────────────────────────────────────
function clearContent() {
  document.getElementById('content-title').textContent = '—';
  document.getElementById('content-from').textContent = '—';
  document.getElementById('content-to').textContent = '';
  document.getElementById('content-time').textContent = '';
  document.getElementById('content-body').textContent = '';
  updateContentStar();
}

function updateContentStar() {
  const el = document.getElementById('content-star');
  const on = state.current && state.current.starred === 1;
  el.className = `fa-${on ? 'solid' : 'regular'} fa-star star${on ? ' on' : ''}`;
}

async function selectEmail(id) {
  state.selectedId = id;
  renderList();
  try {
    const m = await getJSON(`/api/emails/${encodeURIComponent(id)}`);
    state.current = m;
    document.getElementById('content-title').textContent = m.subject || '(无主题)';
    document.getElementById('content-from').textContent = m.fromAddr;
    document.getElementById('content-to').textContent = `发给 ${senderName(m.toAddr)}`;
    document.getElementById('content-time').textContent = fmtTime(m.createdAt);
    document.getElementById('content-body').textContent = m.body || '';
    updateContentStar();
    // local list copy now read
    const item = state.emails.find((e) => e.id === id);
    if (item) item.isRead = 1;
    loadMe();
  } catch (e) {
    console.error(e);
  }
}

async function toggleCurrentRead() {
  const m = state.current;
  if (!m) return;
  const next = m.isRead !== 1 ? true : false; // if read -> mark unread
  const read = m.isRead === 1 ? false : true;
  try {
    await postJSON(`/api/emails/${encodeURIComponent(m.id)}/read`, { read });
    m.isRead = read ? 1 : 0;
    const item = state.emails.find((e) => e.id === m.id);
    if (item) item.isRead = m.isRead;
    showToast(read ? '已标为已读' : '已标为未读');
    renderList();
    loadMe();
  } catch (e) {
    showToast(`操作失败：${e.message}`);
  }
}

async function moveCurrent(folder) {
  const m = state.current;
  if (!m) return;
  try {
    await postJSON(`/api/emails/${encodeURIComponent(m.id)}/move`, { folder });
    showToast(`已移动到${FOLDER_LABEL[folder] || folder}`);
    await loadFolder(state.folder);
    loadMe();
  } catch (e) {
    showToast(`操作失败：${e.message}`);
  }
}

async function deleteCurrent() {
  const m = state.current;
  if (!m) return;
  try {
    await postJSON(`/api/emails/${encodeURIComponent(m.id)}/delete`, { userId: USER_ID });
    showToast('已删除 1 封邮件');
    await loadFolder(state.folder);
    loadMe();
  } catch (e) {
    showToast(`操作失败：${e.message}`);
  }
}

// ── compose modal ──────────────────────────────────────────────────────────
function openCompose(opts) {
  const o = opts || {};
  document.getElementById('compose-title').textContent = o.title || '写邮件';
  document.getElementById('compose-to').value = o.to || '';
  document.getElementById('compose-subject').value = o.subject || '';
  document.getElementById('compose-body').value = o.body || '';
  document.getElementById('compose-overlay').classList.add('open');
  document.getElementById(o.to ? 'compose-body' : 'compose-to').focus();
}

function closeCompose() {
  document.getElementById('compose-overlay').classList.remove('open');
}

function composeValues() {
  return {
    to: document.getElementById('compose-to').value.trim(),
    subject: document.getElementById('compose-subject').value.trim(),
    body: document.getElementById('compose-body').value,
  };
}

async function doSend() {
  const { to, subject, body } = composeValues();
  if (!to) { showToast('请填写收件人'); return; }
  try {
    await postJSON('/api/send', { userId: USER_ID, to, subject, body });
    closeCompose();
    showToast(`已发送邮件至 ${to}`);
    loadMe();
    if (state.folder === 'sent') loadFolder('sent');
  } catch (e) {
    showToast(`发送失败：${e.message}`);
  }
}

async function doDraft() {
  const { to, subject, body } = composeValues();
  try {
    await postJSON('/api/drafts', { userId: USER_ID, to, subject, body });
    closeCompose();
    showToast('草稿已保存');
    loadMe();
    if (state.folder === 'drafts') loadFolder('drafts');
  } catch (e) {
    showToast(`保存失败：${e.message}`);
  }
}

function replyTo(all) {
  const m = state.current;
  if (!m) { showToast('请先选择一封邮件'); return; }
  const subject = /^re:/i.test(m.subject) ? m.subject : `Re: ${m.subject}`;
  const body = `\n\n--- 原邮件 ---\n发件人: ${m.fromAddr}\n时间: ${fmtTime(m.createdAt)}\n主题: ${m.subject}\n\n${m.body}`;
  openCompose({ title: all ? '回复全部' : '回复', to: m.fromAddr, subject, body });
}

function forwardCurrent() {
  const m = state.current;
  if (!m) { showToast('请先选择一封邮件'); return; }
  const subject = /^fwd:/i.test(m.subject) ? m.subject : `Fwd: ${m.subject}`;
  const body = `\n\n---------- 转发邮件 ----------\n发件人: ${m.fromAddr}\n时间: ${fmtTime(m.createdAt)}\n主题: ${m.subject}\n\n${m.body}`;
  openCompose({ title: '转发', to: '', subject, body });
}

// ── popup menu primitive ────────────────────────────────────────────────────
let activeMenu = null;
function closeMenu() {
  if (activeMenu) {
    activeMenu.remove();
    activeMenu = null;
    document.removeEventListener('click', onDocClick, true);
  }
}
function onDocClick(e) {
  if (activeMenu && !activeMenu.contains(e.target)) closeMenu();
}
function openMenu(anchor, items) {
  closeMenu();
  const menu = document.createElement('div');
  menu.className = 'popup-menu';
  items.forEach((it) => {
    if (it.sep) {
      const s = document.createElement('div');
      s.className = 'sep';
      menu.appendChild(s);
      return;
    }
    const d = document.createElement('div');
    d.className = 'mi' + (it.danger ? ' danger' : '');
    const icon = document.createElement('i');
    icon.className = it.icon || '';
    const span = document.createElement('span');
    span.textContent = it.label;
    d.appendChild(icon);
    d.appendChild(span);
    d.addEventListener('click', (ev) => { ev.stopPropagation(); closeMenu(); it.onClick(); });
    menu.appendChild(d);
  });
  document.body.appendChild(menu);
  const r = anchor.getBoundingClientRect();
  menu.style.top = `${r.bottom + 4 + window.scrollY}px`;
  menu.style.left = `${r.left + window.scrollX}px`;
  const mr = menu.getBoundingClientRect();
  if (mr.right > window.innerWidth - 8) {
    menu.style.left = `${window.innerWidth - mr.width - 8 + window.scrollX}px`;
  }
  activeMenu = menu;
  setTimeout(() => document.addEventListener('click', onDocClick, true), 0);
}

function folderMenuItems(onPick) {
  return [
    { label: '收件箱', icon: 'fa-solid fa-inbox', onClick: () => onPick('inbox') },
    { label: '已发送', icon: 'fa-regular fa-paper-plane', onClick: () => onPick('sent') },
    { label: '草稿箱', icon: 'fa-regular fa-file-lines', onClick: () => onPick('drafts') },
    { label: '垃圾箱', icon: 'fa-regular fa-trash-can', onClick: () => onPick('trash') },
  ];
}

// ── search ──────────────────────────────────────────────────────────────
async function doSearch(q) {
  if (!q.trim()) {
    loadFolder(state.folder);
    return;
  }
  const { emails } = await getJSON(`/api/search?q=${encodeURIComponent(q)}&userId=${USER_ID}`);
  state.emails = emails;
  state.selection.clear();
  state.selectedId = emails.length ? emails[0].id : null;
  if (emails.length) selectEmail(emails[0].id);
  else { state.current = null; clearContent(); renderList(); }
}

// ── toast ──────────────────────────────────────────────────────────────
let toastTimer = null;
function showToast(text) {
  const toast = document.getElementById('toast');
  document.getElementById('toast-text').textContent = text;
  toast.style.display = 'flex';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.style.display = 'none'; }, 4000);
}

// ── AI chat ──────────────────────────────────────────────────────────────
function nowHM() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function appendChat(role, text) {
  const area = document.getElementById('chat-area');
  const wrap = document.createElement('div');
  wrap.className = `chat-message ${role}`;
  const info = role === 'user'
    ? `${nowHM()} 你`
    : `<i class="fa-solid fa-robot ai-avatar"></i> AI 助手 ${nowHM()}`;
  wrap.innerHTML = `<div class="chat-info">${info}</div><div class="chat-bubble"></div>`;
  wrap.querySelector('.chat-bubble').textContent = text;
  area.appendChild(wrap);
  area.scrollTop = area.scrollHeight;
  return wrap;
}

function toastForToolCalls(toolCalls) {
  const ops = (toolCalls || []).map((t) => t.name);
  const count = (name) => ops.filter((n) => n === name).length;
  if (count('delete_email')) showToast(`已删除 ${count('delete_email')} 封邮件`);
  else if (count('forward_email')) showToast(`已转发 ${count('forward_email')} 封邮件`);
  else if (count('send_email')) showToast(`已发送 ${count('send_email')} 封邮件`);
  if (ops.some((n) => ['delete_email', 'forward_email', 'send_email'].includes(n))) {
    loadFolder(state.folder);
    loadMe();
  }
}

async function sendChat(text) {
  const msg = text.trim();
  if (!msg) return;
  appendChat('user', msg);
  state.history.push({ role: 'user', content: msg });

  const typing = appendChat('ai', '正在思考…');
  typing.querySelector('.chat-bubble').classList.add('typing');

  try {
    const r = await fetch('/chat?format=json', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ message: msg, userId: USER_ID, history: state.history.slice(0, -1) }),
    });
    const data = await r.json();
    const reply = data.response || data.error || '（无回复）';
    const bubble = typing.querySelector('.chat-bubble');
    bubble.classList.remove('typing');
    bubble.textContent = reply;
    state.history.push({ role: 'assistant', content: reply });
    toastForToolCalls(data.tool_calls);
  } catch (e) {
    const bubble = typing.querySelector('.chat-bubble');
    bubble.classList.remove('typing');
    bubble.textContent = `请求失败：${e.message}`;
  }
}

// ── auth UI ────────────────────────────────────────────────────────────────
let authMode = 'login'; // 'login' | 'register'

function showAuth() {
  document.getElementById('app-root').style.display = 'none';
  document.getElementById('auth-overlay').classList.add('open');
  setAuthMode('login');
  document.getElementById('auth-email').focus();
}

function hideAuth() {
  document.getElementById('auth-overlay').classList.remove('open');
  document.getElementById('app-root').style.display = '';
}

function setAuthMode(mode) {
  authMode = mode;
  const isReg = mode === 'register';
  document.getElementById('auth-name-row').style.display = isReg ? '' : 'none';
  document.getElementById('auth-submit').textContent = isReg ? '注册并登录' : '登录';
  document.getElementById('auth-switch-text').textContent = isReg ? '已有账号？' : '还没有账号？';
  document.getElementById('auth-switch-link').textContent = isReg ? '去登录' : '去注册';
  document.getElementById('auth-tab-login').classList.toggle('active', !isReg);
  document.getElementById('auth-tab-register').classList.toggle('active', isReg);
  setAuthError('');
}

function setAuthError(msg) {
  const el = document.getElementById('auth-error');
  el.textContent = msg || '';
  el.style.display = msg ? '' : 'none';
}

async function submitAuth() {
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  const name = document.getElementById('auth-name').value.trim();
  if (!email || !password) { setAuthError('请填写邮箱和密码'); return; }
  if (authMode === 'register' && !name) { setAuthError('请填写姓名'); return; }

  const url = authMode === 'register' ? '/api/auth/register' : '/api/auth/login';
  const payload = authMode === 'register' ? { name, email, password } : { email, password };
  try {
    const { token, user } = await postJSON(url, payload);
    setAuth(token, user);
    setAuthError('');
    hideAuth();
    startApp();
    showToast(`欢迎，${user.name || user.id}`);
  } catch (e) {
    setAuthError(e.message || '认证失败');
  }
}

async function logout() {
  try { await postJSON('/api/auth/logout', {}); } catch (e) { /* ignore */ }
  clearAuth();
  // reset transient state
  state.emails = [];
  state.selectedId = null;
  state.current = null;
  state.selection.clear();
  state.history = [];
  document.getElementById('chat-area').innerHTML = '';
  showAuth();
}

// Validate a restored session; falls back to the login screen if invalid.
async function tryRestoreSession() {
  const stored = loadStoredAuth();
  if (!stored || !stored.token) return false;
  AUTH_TOKEN = stored.token;
  try {
    const { user } = await getJSON('/api/auth/session');
    setAuth(stored.token, user);
    return true;
  } catch (e) {
    clearAuth();
    return false;
  }
}

function startApp() {
  loadMe();
  loadFolder('inbox');
}

// ── wiring ──────────────────────────────────────────────────────────────
function init() {
  document.querySelectorAll('.nav-item[data-folder]').forEach((el) => {
    el.addEventListener('click', () => loadFolder(el.dataset.folder));
  });

  // placeholder sidebar items (custom folders / tags / + buttons): graceful toast
  document.querySelectorAll('[data-placeholder]').forEach((el) => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      showToast(`「${el.dataset.placeholder}」为演示占位，暂无数据`);
    });
  });

  // compose / write
  document.getElementById('write-btn').addEventListener('click', () => openCompose({ title: '写邮件' }));
  document.getElementById('compose-close').addEventListener('click', closeCompose);
  document.getElementById('compose-cancel').addEventListener('click', closeCompose);
  document.getElementById('compose-send').addEventListener('click', doSend);
  document.getElementById('compose-draft').addEventListener('click', doDraft);
  document.getElementById('compose-overlay').addEventListener('click', (e) => {
    if (e.target.id === 'compose-overlay') closeCompose();
  });

  // reply box
  document.getElementById('reply-btn').addEventListener('click', () => replyTo(false));
  document.getElementById('reply-all-btn').addEventListener('click', () => replyTo(true));
  document.getElementById('forward-btn').addEventListener('click', forwardCurrent);

  // content header actions
  document.getElementById('content-star').addEventListener('click', () => {
    if (state.current) toggleStar(state.current.id);
  });
  document.getElementById('content-reply').addEventListener('click', () => replyTo(false));
  document.getElementById('content-more').addEventListener('click', (e) => {
    e.stopPropagation();
    if (!state.current) { showToast('请先选择一封邮件'); return; }
    openMenu(e.currentTarget, [
      { label: '回复', icon: 'fa-solid fa-reply', onClick: () => replyTo(false) },
      { label: '转发', icon: 'fa-solid fa-share', onClick: forwardCurrent },
      { label: state.current.isRead === 1 ? '标为未读' : '标为已读', icon: 'fa-regular fa-envelope', onClick: toggleCurrentRead },
      { label: '移动到…', icon: 'fa-solid fa-folder-open', onClick: () => openMenu(e.currentTarget, folderMenuItems(moveCurrent)) },
      { sep: true },
      { label: '删除', icon: 'fa-regular fa-trash-can', danger: true, onClick: deleteCurrent },
    ]);
  });

  // bulk toolbar
  document.getElementById('select-all').addEventListener('click', toggleSelectAll);
  document.getElementById('bulk-delete').addEventListener('click', () => bulk('delete'));
  document.getElementById('bulk-read').addEventListener('click', () => bulk('read'));
  document.getElementById('bulk-move').addEventListener('click', (e) => {
    if (state.selection.size === 0) { showToast('请先勾选邮件'); return; }
    openMenu(e.currentTarget, folderMenuItems((f) => bulk('move', { folder: f })));
  });
  document.getElementById('bulk-more').addEventListener('click', (e) => {
    if (state.selection.size === 0) { showToast('请先勾选邮件'); return; }
    openMenu(e.currentTarget, [
      { label: '标为未读', icon: 'fa-regular fa-envelope', onClick: () => bulk('unread') },
      { label: '加星标', icon: 'fa-solid fa-star', onClick: () => bulk('star') },
      { label: '取消星标', icon: 'fa-regular fa-star', onClick: () => bulk('unstar') },
    ]);
  });

  // search
  const search = document.getElementById('search-input');
  search.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') doSearch(search.value);
  });

  // AI chat
  const input = document.getElementById('chat-input');
  document.getElementById('send-btn').addEventListener('click', () => {
    sendChat(input.value); input.value = '';
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChat(input.value); input.value = '';
    }
  });
  document.querySelectorAll('.action-chip').forEach((chip) => {
    chip.addEventListener('click', () => sendChat(chip.dataset.prompt));
  });

  document.getElementById('toast-close').addEventListener('click', () => {
    document.getElementById('toast').style.display = 'none';
  });

  // Esc closes modal/menu
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { closeCompose(); closeMenu(); }
  });

  // auth modal wiring
  document.getElementById('auth-submit').addEventListener('click', submitAuth);
  document.getElementById('auth-switch-link').addEventListener('click', () => {
    setAuthMode(authMode === 'login' ? 'register' : 'login');
  });
  document.getElementById('auth-tab-login').addEventListener('click', () => setAuthMode('login'));
  document.getElementById('auth-tab-register').addEventListener('click', () => setAuthMode('register'));
  document.getElementById('auth-password').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submitAuth();
  });
  document.getElementById('logout-btn').addEventListener('click', logout);

  // Bootstrap: restore a saved session or show the login screen.
  tryRestoreSession().then((ok) => {
    if (ok) startApp();
    else showAuth();
  });
}

document.addEventListener('DOMContentLoaded', init);

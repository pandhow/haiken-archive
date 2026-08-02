// 海垦日报历史归档 · SPA runtime
// 外壳已加载 → 拉 manifest → 渲染列表 → 哈希路由 → iframe 载入当日 HTML

const MANIFEST_URL = 'data/manifest.json';
const INDEX_URL = 'data/index.json';
let ISSUES = [];        // 全部期次（按 date 降序）
let INDEX_MAP = {};     // date -> 正文纯文本（用于搜内容关键词）
let activeDate = null;

const $list = document.getElementById('issueList');
const $count = document.getElementById('issueCount');
const $latest = document.getElementById('latestDate');
const $search = document.getElementById('searchBox');
const $frame = document.getElementById('issueFrame');
const $empty = document.getElementById('emptyState');
const $about = document.getElementById('aboutPanel');

async function boot() {
  try {
    const res = await fetch(MANIFEST_URL, { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    ISSUES = (data.issues || []).slice().sort((a, b) => (a.date < b.date ? 1 : -1));
  } catch (e) {
    $list.innerHTML = `<li class="loading" style="color:#ff8a80">⚠️ 加载 manifest 失败：${e.message}<br><span style="font-size:11px;color:#5d6e8a">需通过 http 协议访问（见 README）</span></li>`;
    return;
  }
  $count.textContent = ISSUES.length;
  $latest.textContent = ISSUES[0] ? ISSUES[0].date : '—';

  // 内容索引（用于搜正文关键词）。失败不影响元数据搜索。
  try {
    const ri = await fetch(INDEX_URL, { cache: 'no-store' });
    if (ri.ok) {
      const idx = await ri.json();
      (idx.issues || []).forEach(it => { INDEX_MAP[it.date] = it.text || ''; });
    }
  } catch (e) { /* 忽略：仅正文搜索不可用 */ }

  renderList(ISSUES);
  route();                       // 按 URL hash 载入
  window.addEventListener('hashchange', route);
  $search.addEventListener('input', onSearch);
}

function renderList(arr) {
  if (!arr.length) {
    $list.innerHTML = `<li class="loading">无匹配期次</li>`;
    return;
  }
  $list.innerHTML = arr.map(it => `
    <li class="issue-item${it.date === activeDate ? ' active' : ''}" data-date="${it.date}">
      <div><span class="date">${it.date}</span><span class="no">第 ${pad(it.issue_no)} 期</span></div>
      <div class="title">${esc(it.title || '(无标题)')}</div>
      ${(it.tags || []).slice(0, 4).map(t => `<span class="tag">${esc(t)}</span>`).join('')}
    </li>`).join('');
  $list.querySelectorAll('.issue-item').forEach(li => {
    li.addEventListener('click', () => { location.hash = '#/' + li.dataset.date; });
  });
}

function pad(n) { return String(n).padStart(3, '0'); }

function onSearch() {
  const q = $search.value.trim().toLowerCase();
  if (!q) { renderList(ISSUES); return; }
  const hit = ISSUES.filter(it =>
    (it.title || '').toLowerCase().includes(q) ||
    (it.date || '').includes(q) ||
    (it.tags || []).some(t => t.toLowerCase().includes(q)) ||
    String(it.issue_no).includes(q) ||
    (INDEX_MAP[it.date] || '').toLowerCase().includes(q));  // 新增：搜右侧正文
  renderList(hit);
}

function route() {
  const h = location.hash.replace(/^#\/?/, '');
  if (h === 'about') { showAbout(); return; }
  if (!h) { showEmpty(); return; }
  const it = ISSUES.find(x => x.date === h);
  if (!it) { showEmpty(`找不到 ${h} 这一期的日报`); return; }
  loadIssue(it);
}

function loadIssue(it) {
  activeDate = it.date;
  document.querySelectorAll('.issue-item').forEach(li =>
    li.classList.toggle('active', li.dataset.date === it.date));
  $about.hidden = true;
  $empty.hidden = true;
  $frame.hidden = false;
  $frame.src = it.file;
  document.title = `海垦日报 · ${it.date}（第 ${pad(it.issue_no)} 期）`;
  // 滚动列表到当前项
  const el = document.querySelector(`.issue-item[data-date="${it.date}"]`);
  if (el) el.scrollIntoView({ block: 'nearest' });
}

function showEmpty(msg) {
  activeDate = null;
  document.querySelectorAll('.issue-item').forEach(li => li.classList.remove('active'));
  $frame.hidden = true;
  $about.hidden = true;
  $empty.hidden = false;
  if (msg) $empty.querySelector('p').textContent = msg;
  document.title = '海垦日报 · 历史归档';
}

function showAbout() {
  activeDate = null;
  document.querySelectorAll('.issue-item').forEach(li => li.classList.remove('active'));
  $frame.hidden = true;
  $empty.hidden = true;
  $about.hidden = false;
  document.title = '关于 · 海垦日报历史归档';
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

// 手机端：把 iframe 高度自适应为内容高度，让整页只滚动一次（消除 iframe 内部滚动）
function autoSizeFrame() {
  if (!window.matchMedia || !window.matchMedia('(max-width:600px)').matches) {
    $frame.style.height = '';   // 桌面端恢复绝对填充
    return;
  }
  try {
    const doc = $frame.contentDocument || ($frame.contentWindow && $frame.contentWindow.document);
    if (!doc) return;
    const h = Math.max(
      doc.body ? doc.body.scrollHeight : 0,
      doc.documentElement ? doc.documentElement.scrollHeight : 0
    );
    if (h) $frame.style.height = h + 'px';
  } catch (e) { /* 跨域等异常忽略 */ }
}
$frame.addEventListener('load', autoSizeFrame);
window.addEventListener('resize', autoSizeFrame);

boot();

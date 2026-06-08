/* UniPulse v3 — 前端交互逻辑 (优化版) */
const API = '/api';
let sessionId = localStorage.getItem('unipulse_session') || (() => {
  const id = 'sess_' + Math.random().toString(36).slice(2, 10);
  localStorage.setItem('unipulse_session', id);
  return id;
})();

// ── 路由 ──
let currentPage = 'home';
let currentUniPage = 1;
let currentForumPage = 1;

function navigate(page, params = {}) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(n => n.classList.remove('active'));
  const pageEl = document.getElementById('page-' + page);
  if (pageEl) pageEl.classList.add('active');
  const navLink = document.querySelector(`.nav-link[data-page="${page}"]`);
  if (navLink) navLink.classList.add('active');
  currentPage = page;
  window.scrollTo({ top: 0, behavior: 'smooth' });

  if (page === 'home') loadHome();
  else if (page === 'universities') loadUniversities(1);
  else if (page === 'uni-detail') loadUniDetail(params.id);
  else if (page === 'programs') loadProgramsFull();
  else if (page === 'program-detail') loadProgramDetail(params.name);
  else if (page === 'forum') loadForum(1);
  else if (page === 'post-detail') loadPostDetail(params.id);
  else if (page === 'favorites') loadFavorites();
  else if (page === 'search') performSearch(params.q || '');
}

document.addEventListener('click', e => {
  const link = e.target.closest('[data-page]');
  if (link) {
    e.preventDefault();
    const page = link.dataset.page;
    const id = link.dataset.id;
    const name = link.dataset.name;
    navigate(page, { id, name });
  }
  const closeBtn = e.target.closest('.close-btn');
  if (closeBtn) closeBtn.closest('.modal').remove();
});

// ── API ──
async function apiGet(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

// ── Toast ──
function showToast(msg, type = 'success') {
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3200);
}

// ── 工具 ──
function tagClass(type) {
  const map = { gold:'tag-gold', blue:'tag-blue', red:'tag-red', green:'tag-green', purple:'tag-purple', cyan:'tag-cyan', orange:'tag-orange', pink:'tag-pink' };
  return map[type] || 'tag-blue';
}

function salaryClass(salary) {
  if (salary >= 20000) return 'salary-high';
  if (salary >= 14000) return 'salary-mid';
  return 'salary-low';
}

function salaryLabel(salary) {
  if (!salary) return '—';
  return (salary >= 1000 ? '¥' + (salary / 1000).toFixed(1) + 'k' : salary + '¥') + '/月';
}

function fmtNumber(n) {
  if (!n) return '—';
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w';
  return n.toLocaleString();
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function relativeTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  const now = new Date();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return '刚刚';
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
  if (diff < 86400 * 7) return Math.floor(diff / 86400) + '天前';
  return d.toLocaleDateString('zh-CN');
}

function toggleFav(uniId, btn) {
  const favs = JSON.parse(localStorage.getItem('unipulse_favs') || '[]');
  const idx = favs.indexOf(uniId);
  if (idx >= 0) {
    favs.splice(idx, 1);
    btn.textContent = '⭐ 收藏';
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-ghost');
    showToast('已取消收藏');
  } else {
    favs.push(uniId);
    btn.textContent = '⭐ 已收藏';
    btn.classList.add('btn-primary');
    btn.classList.remove('btn-ghost');
    showToast('已收藏高校');
  }
  localStorage.setItem('unipulse_favs', JSON.stringify(favs));
}

function isFaved(uniId) {
  return JSON.parse(localStorage.getItem('unipulse_favs') || '[]').includes(uniId);
}

// ── 骨架屏 ──
function skeletonUniCard() {
  return `<div class="uni-card">
    <div class="uni-card-top">
      <div class="skeleton" style="width:46px;height:46px;border-radius:10px"></div>
      <div style="flex:1">
        <div class="skeleton" style="width:60%;height:14px;margin-bottom:6px"></div>
        <div class="skeleton" style="width:40%;height:11px"></div>
      </div>
      <div class="skeleton" style="width:36px;height:20px;border-radius:999px"></div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.5rem;padding:0.8rem 0;border-top:1px solid var(--border);border-bottom:1px solid var(--border)">
      <div class="skeleton" style="height:28px;border-radius:6px"></div>
      <div class="skeleton" style="height:28px;border-radius:6px"></div>
      <div class="skeleton" style="height:28px;border-radius:6px"></div>
    </div>
    <div style="display:flex;gap:0.3rem;margin-top:0.5rem">
      <div class="skeleton" style="width:48px;height:18px;border-radius:999px"></div>
      <div class="skeleton" style="width:60px;height:18px;border-radius:999px"></div>
    </div>
  </div>`;
}

function animateValue(el, target, duration = 1200) {
  const start = 0;
  const startTime = performance.now();
  function update(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.round(start + (target - start) * eased);
    el.textContent = typeof target === 'string' ? target : current.toLocaleString();
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

// ── 通用卡片渲染 ──
function renderUniCard(u) {
  const stars = u.stars || 4;
  const starsHtml = '★'.repeat(Math.floor(stars)) + '☆'.repeat(5 - Math.floor(stars));
  const tagsHtml = (u.tags || []).slice(0, 3).map(t => `<span class="tag ${tagClass(t.type || 'blue')}">${escapeHtml(t.text)}</span>`).join('');
  const favBtn = isFaved(u.id) ? '⭐ 已收藏' : '⭐ 收藏';
  const favClass = isFaved(u.id) ? 'btn-primary' : 'btn-ghost';
  return `
    <div class="uni-card" data-page="uni-detail" data-id="${u.id}">
      <div class="uni-card-top">
        <div class="uni-logo" style="background:${escapeHtml(u.logo || '#3b82f6')}">${escapeHtml(u.initials || u.cn?.charAt(0) || 'U')}</div>
        <div class="uni-name-group">
          <div class="uni-cn">${escapeHtml(u.cn)}</div>
          <div class="uni-loc">📍 ${escapeHtml(u.loc)} · ${escapeHtml(u.type)}</div>
        </div>
        <span class="uni-rank-badge">#${u.rank}</span>
      </div>
      <div class="uni-metrics">
        <div class="uni-metric"><div class="uni-metric-val">${u.gaokao_score ? u.gaokao_score + '分' : '—'}</div><div class="uni-metric-label">高考分数线</div></div>
        <div class="uni-metric"><div class="uni-metric-val">${u.avg_salary ? '¥' + (u.avg_salary / 1000).toFixed(1) + 'k' : '—'}</div><div class="uni-metric-label">平均月薪</div></div>
        <div class="uni-metric"><div class="uni-metric-val">${u.employment_rate ? u.employment_rate + '%' : '—'}</div><div class="uni-metric-label">就业率</div></div>
      </div>
      <div class="uni-tags">${tagsHtml}</div>
      <div class="uni-card-actions">
        <button class="btn btn-primary btn-sm" data-page="uni-detail" data-id="${u.id}">查看详情 →</button>
        <button class="btn ${favClass} btn-sm fav-btn" data-uni="${u.id}">${favBtn}</button>
      </div>
    </div>`;
}

// ── 首页 ──
async function loadHome() {
  // 骨架屏
  document.getElementById('heroStats').innerHTML = Array(4).fill('<div class="stat-pill skeleton" style="width:90px;height:32px"></div>').join('');
  document.getElementById('hotUnis').innerHTML = Array(6).fill(skeletonUniCard()).join('');
  document.getElementById('programGrid').innerHTML = Array(8).fill('<div class="program-card skeleton" style="height:100px"></div>').join('');
  document.getElementById('forumPreview').innerHTML = Array(3).fill('<div class="skeleton" style="height:80px;border-radius:14px;margin-bottom:0.8rem"></div>').join('');

  try {
    const [stats, hot, progs, posts] = await Promise.all([
      apiGet('/stats'),
      apiGet('/universities?sort=rank&order=asc&limit=6'),
      apiGet('/programs'),
      apiGet('/forum/posts?sort=hot&limit=5')
    ]);

    // Stats 动画
    const statsEl = document.getElementById('heroStats');
    statsEl.innerHTML = '';
    const statData = [
      { icon:'🏫', val: stats.universities, suffix:' 所高校', label:`${stats.universities} 所高校` },
      { icon:'💼', val: stats.employment_records, suffix:' 条就业数据', label:`${stats.employment_records} 条就业数据` },
      { icon:'📈', val: stats.avg_salary, prefix:'¥', suffix:'k 均薪', label:`¥${(stats.avg_salary/1000).toFixed(1)}k 均薪` },
      { icon:'📖', val: stats.avg_employment_rate, suffix:'% 就业率', label:`${stats.avg_employment_rate}% 就业率` },
    ];

    // 延迟渲染每个 stat pill 并动画
    statData.forEach((s, i) => {
      setTimeout(() => {
        const pill = document.createElement('div');
        pill.className = 'stat-pill';
        pill.textContent = s.label;
        pill.style.opacity = '0';
        pill.style.transform = 'translateY(10px)';
        statsEl.appendChild(pill);
        requestAnimationFrame(() => {
          pill.style.transition = 'all 0.4s ease';
          pill.style.opacity = '1';
          pill.style.transform = 'translateY(0)';
        });
      }, i * 120);
    });

    // 高校动画
    const hotGrid = document.getElementById('hotUnis');
    hotGrid.innerHTML = (hot.data || []).map(renderUniCard).join('');
    animateCards(hotGrid);

    // 专业
    document.getElementById('programGrid').innerHTML = (progs || []).slice(0, 10).map((p, i) => `
      <div class="program-card" data-page="program-detail" data-name="${escapeHtml(p.name)}" style="animation:cardFade 0.4s ease ${i*60}ms both">
        <div class="program-icon">${escapeHtml(p.icon || '📚')}</div>
        <div class="program-name">${escapeHtml(p.name)}</div>
        <div class="program-count">${p.count} 所高校</div>
      </div>`).join('');

    // 论坛预览
    document.getElementById('forumPreview').innerHTML = (posts.data || []).map(p => `
      <div class="forum-post-card" data-page="post-detail" data-id="${p.id}">
        <div class="forum-post-title">${escapeHtml(p.title)}</div>
        <div class="forum-post-meta">
          <span>👤 ${escapeHtml(p.author)}</span>
          <span>🏷️ ${escapeHtml(p.category)}</span>
          <span>👁️ ${p.views}</span>
          <span>❤️ ${p.likes}</span>
        </div>
      </div>`).join('');
    attachFavBtns();
  } catch(e) {
    console.error(e);
    document.getElementById('hotUnis').innerHTML = '<p style="color:var(--red);text-align:center;padding:2rem">加载失败，请刷新重试</p>';
  }
}

function animateCards(container) {
  const cards = container.querySelectorAll('.uni-card');
  cards.forEach((card, i) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';
    setTimeout(() => {
      card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    }, i * 80);
  });
}

// ── 高校列表 ──
async function loadUniversities(page = 1) {
  currentUniPage = page;
  const q = document.getElementById('uniSearch')?.value || '';
  const region = document.getElementById('filterRegion')?.value || '';
  const level = document.getElementById('filterLevel')?.value || '';
  const type = document.getElementById('filterType')?.value || '';
  const sortEl = document.getElementById('sortUni');
  const sortParts = sortEl ? sortEl.value.split('-') : ['rank', 'asc'];
  const sort = sortParts[0], order = sortParts[1];
  const offset = (page - 1) * 20;

  // 骨架屏
  const grid = document.getElementById('uniGrid');
  grid.innerHTML = Array(12).fill(skeletonUniCard()).join('');

  try {
    const data = await apiGet(`/universities?q=${encodeURIComponent(q)}&region=${region}&level=${level}&type=${type}&sort=${sort}&order=${order}&limit=20&offset=${offset}`);
    const total = data.total || 0;
    document.getElementById('uniResultsInfo').textContent = `共 ${total} 所高校，第 ${page} 页`;
    grid.innerHTML = (data.data || []).map(renderUniCard).join('');
    animateCards(grid);

    const totalPages = Math.ceil(total / 20);
    const pagEl = document.getElementById('uniPagination');
    if (totalPages > 1) {
      let pages = [];
      for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || Math.abs(i - page) <= 2) pages.push(i);
        else if (pages[pages.length - 1] !== '...') pages.push('...');
      }
      pagEl.innerHTML = pages.map(p => p === '...' ? `<span class="btn btn-ghost btn-sm" style="pointer-events:none">...</span>` :
        `<button class="btn btn-sm ${p === page ? 'btn-primary' : 'btn-ghost'}" onclick="loadUniversities(${p})">${p}</button>`
      ).join('');
    } else { pagEl.innerHTML = ''; }
    attachFavBtns();
  } catch(e) {
    grid.innerHTML = '<p style="color:var(--red);text-align:center;padding:2rem">加载失败</p>';
  }
}

function attachFavBtns() {
  document.querySelectorAll('.fav-btn').forEach(btn => {
    btn.onclick = e => {
      e.stopPropagation();
      e.preventDefault();
      const uniId = parseInt(btn.dataset.uni);
      toggleFav(uniId, btn);
    };
  });
}

// ── 高校详情 ──
async function loadUniDetail(id) {
  document.getElementById('uniDetailContent').innerHTML = `
    <div style="display:flex;gap:1rem;align-items:center;margin-bottom:2rem">
      <button class="btn btn-ghost btn-sm" onclick="navigate('universities')">← 返回</button>
    </div>
    <div style="display:flex;gap:1rem;align-items:center;margin-bottom:2rem;flex-wrap:wrap">
      <div class="skeleton" style="width:80px;height:80px;border-radius:14px;flex-shrink:0"></div>
      <div style="flex:1">
        <div class="skeleton" style="width:50%;height:24px;margin-bottom:8px"></div>
        <div class="skeleton" style="width:70%;height:14px;margin-bottom:6px"></div>
        <div class="skeleton" style="width:60%;height:14px"></div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:0.8rem;margin-bottom:2rem">
      ${Array(6).fill('<div class="skeleton" style="height:70px;border-radius:10px"></div>').join('')}
    </div>`;

  try {
    const u = await apiGet(`/universities/${id}`);
    const tagsHtml = (u.tags || []).map(t => `<span class="tag ${tagClass(t.type || 'blue')}">${escapeHtml(t.text)}</span>`).join('');
    const progHtml = (u.programs || []).map(p => `
      <tr>
        <td>${escapeHtml(p.program_name)}</td>
        <td class="${salaryClass(p.salary_avg)}">${salaryLabel(p.salary_avg)}</td>
        <td class="${salaryClass(p.salary_entry)}">${salaryLabel(p.salary_entry)}</td>
        <td>${p.employment_rate ? p.employment_rate + '%' : '—'}</td>
        <td>${p.prospects ? p.prospects + '/100' : '—'}</td>
      </tr>`).join('');
    const progCatsHtml = (u.program_categories || []).map(p => `<span class="tag tag-blue">${escapeHtml(p.icon)} ${escapeHtml(p.name)}</span>`).join('');
    const favBtn = isFaved(u.id) ? '⭐ 已收藏' : '⭐ 收藏';
    const favClass = isFaved(u.id) ? 'btn-primary' : 'btn-ghost';

    document.getElementById('uniDetailContent').innerHTML = `
      <button class="btn btn-ghost btn-sm" onclick="navigate('universities')" style="margin-bottom:1rem">← 返回列表</button>
      <div class="uni-detail-header">
        <div class="uni-detail-logo" style="background:${escapeHtml(u.logo || '#3b82f6')}">${escapeHtml(u.initials || u.cn?.charAt(0))}</div>
        <div class="uni-detail-info">
          <h1>${escapeHtml(u.cn)} <small style="font-size:0.5em;color:var(--text3)">${escapeHtml(u.name)}</small></h1>
          <div class="uni-meta-row">
            <span class="meta-item">📍 ${escapeHtml(u.loc)} · ${escapeHtml(u.region)}</span>
            <span class="meta-item">🏆 软科排名 #${u.rank}</span>
            <span class="meta-item">🎓 ${escapeHtml(u.level)}</span>
            <span class="meta-item">📖 ${escapeHtml(u.type)}</span>
          </div>
          <div class="uni-tags">${tagsHtml}</div>
        </div>
        <button class="btn ${favClass} fav-btn" data-uni="${u.id}">${favBtn}</button>
      </div>
      <div class="uni-description">${escapeHtml(u.description)}</div>
      ${u.program_categories?.length ? `<div style="margin-bottom:1.5rem"><strong>开设专业：</strong>${progCatsHtml}</div>` : ''}
      <div class="metrics-grid">
        <div class="metric-card"><div class="val">${u.gaokao_score || '—'}</div><div class="lbl">高考分数线</div></div>
        <div class="metric-card"><div class="val">${u.avg_salary ? '¥' + (u.avg_salary/1000).toFixed(1) + 'k' : '—'}</div><div class="lbl">平均月薪</div></div>
        <div class="metric-card"><div class="val">${u.employment_rate ? u.employment_rate + '%' : '—'}</div><div class="lbl">就业率</div></div>
        <div class="metric-card"><div class="val">${u.stars?.toFixed(1) || '—'}</div><div class="lbl">评分</div></div>
        <div class="metric-card"><div class="val">¥${((u.tuition || 5000) / 1000).toFixed(1)}k</div><div class="lbl">年学费(元)</div></div>
        <div class="metric-card"><div class="val">${u.reviews || 0}</div><div class="lbl">评价数</div></div>
      </div>
      ${Object.keys(u.metrics || {}).length ? `
      <h3 style="margin:1.5rem 0 1rem">📊 六维能力图</h3>
      <div class="metrics-grid" style="grid-template-columns:repeat(3,1fr)">
        ${Object.entries(u.metrics || {}).map(([k, v]) => `<div class="metric-card">
          <div class="val">${typeof v === 'number' ? v + '%' : '—'}</div>
          <div class="lbl">${escapeHtml(k)}</div>
          <div class="progress-bar"><div class="progress-fill" style="width:${typeof v === 'number' ? v + '%' : '0'}"></div></div>
        </div>`).join('')}
      </div>` : ''}
      ${u.programs?.length ? `
      <h3 style="margin:1.5rem 0 1rem">💼 各专业就业数据</h3>
      <table class="emp-table">
        <thead><tr><th>专业</th><th>平均月薪</th><th>起步月薪</th><th>就业率</th><th>前景评分</th></tr></thead>
        <tbody>${progHtml}</tbody>
      </table>` : ''}
      ${progCatsHtml ? `<h3 style="margin:1.5rem 0 1rem">🔗 相关专业</h3><div class="uni-tags">${progCatsHtml}</div>` : ''}`;

    attachFavBtns();
    document.querySelectorAll('.progress-fill').forEach(bar => {
      const target = parseFloat(bar.style.width);
      bar.style.width = '0';
      setTimeout(() => { bar.style.width = target + '%'; }, 300);
    });
  } catch(e) {
    document.getElementById('uniDetailContent').innerHTML = `<p style="color:var(--red)">加载失败: ${e.message}</p>`;
  }
}

// ── 专业列表 ──
async function loadProgramsFull() {
  try {
    const progs = await apiGet('/programs');
    const grid = document.getElementById('programGridFull');
    grid.innerHTML = (progs || []).map((p, i) => `
      <div class="program-card" data-page="program-detail" data-name="${escapeHtml(p.name)}" style="animation:cardFade 0.4s ease ${i*50}ms both">
        <div class="program-icon">${escapeHtml(p.icon || '📚')}</div>
        <div class="program-name">${escapeHtml(p.name)}</div>
        <div class="program-count">${p.count} 所高校开设</div>
      </div>`).join('');
  } catch(e) { console.error(e); }
}

// ── 专业详情 ──
async function loadProgramDetail(name) {
  document.getElementById('programDetailContent').innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>加载中...</p></div>';
  try {
    const data = await apiGet(`/programs/${encodeURIComponent(name)}`);
    const uniCards = Object.entries(data.employment || {}).map(([uniName, info]) => {
      const u = info.uni;
      const progs = (info.programs || []).map(p => `
        <tr>
          <td>${escapeHtml(p.program_name)}</td>
          <td class="${salaryClass(p.salary_avg)}">${salaryLabel(p.salary_avg)}</td>
          <td>${p.employment_rate ? p.employment_rate + '%' : '—'}</td>
          <td>${p.prospects ? p.prospects + '/100' : '—'}</td>
        </tr>`).join('');
      return `<div class="uni-card" style="margin-bottom:1rem;cursor:default">
        <h4>${escapeHtml(uniName)} <small style="color:var(--text3)">#${u.rank} · ${escapeHtml(u.level)}</small></h4>
        ${progs ? `<table class="emp-table"><thead><tr><th>专业方向</th><th>平均月薪</th><th>就业率</th><th>前景</th></tr></thead><tbody>${progs}</tbody></table>` : '<p style="color:var(--text3);font-size:0.85rem">暂无就业数据</p>'}
      </div>`;
    }).join('');
    document.getElementById('programDetailContent').innerHTML = `
      <button class="btn btn-ghost btn-sm" onclick="navigate('programs')" style="margin-bottom:1rem">← 返回专业</button>
      <div class="uni-detail-header">
        <div class="program-icon" style="font-size:3rem">${escapeHtml(data.icon || '📚')}</div>
        <div><h1>${escapeHtml(data.name)}</h1><p style="color:var(--text2)">${Object.keys(data.employment || {}).length} 所高校开设此专业</p></div>
      </div>
      ${uniCards || '<p style="color:var(--text3)">暂无详细数据</p>'}`;
  } catch(e) {
    document.getElementById('programDetailContent').innerHTML = `<p style="color:var(--red)">加载失败: ${e.message}</p>`;
  }
}

// ── 论坛 ──
async function loadForum(page = 1) {
  currentForumPage = page;
  const sort = document.getElementById('forumSort')?.value || 'recent';
  const category = document.getElementById('forumCategory')?.value || '';
  const offset = (page - 1) * 20;
  const postsEl = document.getElementById('forumPosts');
  postsEl.innerHTML = Array(5).fill('<div class="skeleton" style="height:100px;border-radius:14px;margin-bottom:0.8rem"></div>').join('');

  try {
    const data = await apiGet(`/forum/posts?sort=${sort}&category=${category}&limit=20&offset=${offset}`);
    const total = data.total || 0;
    postsEl.innerHTML = (data.data || []).map((p, i) => `
      <div class="forum-post-card" data-page="post-detail" data-id="${p.id}" style="animation:cardFade 0.35s ease ${i*60}ms both">
        <div class="forum-post-title">${escapeHtml(p.title)}</div>
        <div class="forum-post-excerpt">${escapeHtml(p.content?.slice(0, 180))}</div>
        <div class="forum-post-meta">
          <span>👤 ${escapeHtml(p.author)}</span>
          <span>🏷️ ${escapeHtml(p.category)}</span>
          <span>👁️ ${p.views}</span>
          <span>❤️ ${p.likes}</span>
          <span>💬 ${p.comment_count || 0}</span>
          <span>${relativeTime(p.created_at)}</span>
        </div>
        <div class="uni-tags" style="margin-top:0.5rem">
          ${(p.tags || []).map(t => `<span class="tag tag-blue">${escapeHtml(t)}</span>`).join('')}
        </div>
      </div>`).join('') || '<div class="empty-state"><p>暂无帖子</p></div>';

    const allTags = (data.data || []).flatMap(p => p.tags || []);
    const tagCounts = {};
    allTags.forEach(t => tagCounts[t] = (tagCounts[t] || 0) + 1);
    document.getElementById('tagCloud').innerHTML = Object.entries(tagCounts).slice(0, 20).map(([t, c]) =>
      `<span class="tag tag-blue">${escapeHtml(t)} (${c})</span>`
    ).join('');

    const totalPages = Math.ceil(total / 20);
    const pagEl = document.getElementById('forumPagination');
    if (totalPages > 1) {
      pagEl.innerHTML = Array.from({length: Math.min(totalPages, 10)}, (_, i) => {
        const p = i + 1;
        return `<button class="btn btn-sm ${p === page ? 'btn-primary' : 'btn-ghost'}" onclick="loadForum(${p})">${p}</button>`;
      }).join('');
    } else { pagEl.innerHTML = ''; }
  } catch(e) { postsEl.innerHTML = '<p style="color:var(--red);text-align:center;padding:2rem">加载失败</p>'; }
}

// ── 帖子详情 ──
async function loadPostDetail(id) {
  document.getElementById('postDetailContent').innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>加载中...</p></div>';
  try {
    const p = await apiGet(`/forum/posts/${id}`);
    const commentsHtml = (p.comments || []).map(c => `
      <div class="comment-card">
        <div class="comment-author">${escapeHtml(c.author)}</div>
        <div class="comment-text">${escapeHtml(c.text)}</div>
        <div class="comment-meta">❤️ ${c.likes} · ${relativeTime(c.created_at)}</div>
      </div>`).join('');
    document.getElementById('postDetailContent').innerHTML = `
      <button class="btn btn-ghost btn-sm" onclick="navigate('forum')" style="margin-bottom:1rem">← 返回论坛</button>
      <div class="forum-post-card" style="cursor:default">
        <div class="post-detail-title">${escapeHtml(p.title)}</div>
        <div class="post-detail-meta">
          <span>👤 ${escapeHtml(p.author)}</span>
          <span>🏷️ ${escapeHtml(p.category)}</span>
          <span>👁️ ${p.views} 浏览</span>
          <span>❤️ ${p.likes} 赞</span>
          <span>💬 ${(p.comments || []).length} 评论</span>
          <span>${relativeTime(p.created_at)}</span>
        </div>
        <div class="uni-tags" style="margin-bottom:1rem">
          ${(p.tags || []).map(t => `<span class="tag tag-blue">${escapeHtml(t)}</span>`).join('')}
        </div>
        <div class="post-detail-content"><p>${escapeHtml(p.content)}</p></div>
        <button class="btn btn-ghost btn-sm" onclick="likePost(${p.id})">❤️ 赞 (${p.likes})</button>
      </div>
      <h3 style="margin:2rem 0 1rem">💬 评论</h3>
      <form id="commentForm" style="margin-bottom:1.5rem">
        <div class="form-group"><textarea id="commentText" class="form-input form-textarea" placeholder="写下你的评论..." required></textarea></div>
        <div class="form-group"><input type="text" id="commentAuthor" class="form-input" placeholder="你的昵称" value="匿名用户"></div>
        <button type="submit" class="btn btn-primary btn-sm">发表评论</button>
      </form>
      <div id="commentsArea">${commentsHtml || '<p style="color:var(--text3)">暂无评论，来说两句？</p>'}</div>`;
    document.getElementById('commentForm')?.addEventListener('submit', e => {
      e.preventDefault();
      submitComment(p.id);
    });
  } catch(e) {
    document.getElementById('postDetailContent').innerHTML = `<p style="color:var(--red)">加载失败: ${e.message}</p>`;
  }
}

async function likePost(id) {
  try {
    await fetch(API + `/forum/posts/${id}/like`, {method:'POST'});
    showToast('👍 点赞成功');
  } catch(e) { showToast('点赞失败', 'error'); }
}

async function submitComment(postId) {
  const text = document.getElementById('commentText')?.value?.trim();
  const author = document.getElementById('commentAuthor')?.value?.trim() || '匿名用户';
  if (!text) return;
  try {
    const r = await fetch(API + `/forum/posts/${postId}/comments`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({author, text})
    });
    if (r.ok) {
      showToast('评论已发布');
      loadPostDetail(postId);
    }
  } catch(e) { showToast('评论失败', 'error'); }
}

// ── 发帖 ──
document.getElementById('newPostBtn')?.addEventListener('click', () => navigate('new-post'));
document.addEventListener('submit', e => {
  if (e.target.id === 'newPostForm') {
    e.preventDefault();
    const title = document.getElementById('postTitle')?.value?.trim();
    const category = document.getElementById('postCategory')?.value;
    const content = document.getElementById('postContent')?.value?.trim();
    const tags = document.getElementById('postTags')?.value?.split(',').map(t => t.trim()).filter(Boolean) || [];
    const author = document.getElementById('postAuthor')?.value?.trim() || '匿名用户';
    if (!title || !content) { showToast('请填写标题和内容', 'error'); return; }
    fetch(API + '/forum/posts', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({title, category, content, tags, author})
    }).then(r => r.json()).then(d => {
      showToast('帖子发布成功！');
      navigate('forum');
    }).catch(() => showToast('发布失败', 'error'));
  }
  if (e.target.id === 'aiReportForm') {
    e.preventDefault();
    generateAiReport();
  }
});

// ── AI报告 ──
async function generateAiReport() {
  const score = parseInt(document.getElementById('aiScore')?.value);
  const province = document.getElementById('aiProvince')?.value || '全国';
  const interests = document.getElementById('aiInterests')?.value?.trim() || '';
  const subjects = document.getElementById('aiSubjects')?.value?.trim() || '';
  const preference = document.getElementById('aiPreference')?.value || '综合';
  if (!score) { showToast('请输入高考分数', 'error'); return; }
  const btn = document.querySelector('#aiReportForm button[type=submit]');
  if (btn) { btn.disabled = true; btn.textContent = '🤖 AI分析中...'; }

  const resultEl = document.getElementById('aiReportResult');
  resultEl.classList.remove('hidden');
  resultEl.innerHTML = `
    <div class="ai-loading">
      <div class="ai-loading-dots">
        <span></span><span></span><span></span>
      </div>
      <p style="color:var(--text2);font-size:0.95rem">正在分析 ${score} 分的最佳选校方案...</p>
      <p style="color:var(--text3);font-size:0.82rem;margin-top:0.5rem">结合 ${province} 考生数据，为你匹配最优高校</p>
    </div>`;

  try {
    const data = await apiGet(`/ai-report?score=${score}&province=${encodeURIComponent(province)}&interests=${encodeURIComponent(interests)}&subjects=${encodeURIComponent(subjects)}&preference=${encodeURIComponent(preference)}`);
    renderAiReport(data);
  } catch(e) {
    resultEl.innerHTML = `<p style="color:var(--red);padding:1rem">报告生成失败: ${e.message}</p>`;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '生成选校报告 🚀'; }
  }
}

function renderAiReport(data) {
  const el = document.getElementById('aiReportResult');
  el.classList.remove('hidden');
  const groups = [
    { label:'🚀 冲一冲（分数线略高于你的分数）', key:'冲', color:'var(--yellow)' },
    { label:'🎯 稳一稳（分数线接近你的分数）', key:'稳', color:'var(--green)' },
    { label:'🛡️ 保一保（分数线低于你的分数）', key:'保', color:'var(--accent)' },
  ];
  let html = `<div class="report-section" style="animation:cardFade 0.5s ease">
    <h3>📊 选校报告 — ${data.score}分 · ${data.province} · ${data.preference}</h3>
    <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem;padding:0.8rem;background:var(--surface2);border-radius:var(--radius-sm)">
      <div style="flex:1;text-align:center;padding:0.5rem">
        <div style="font-size:1.3rem;font-weight:800;color:var(--yellow)">${data.suggestions?.冲?.length || 0}</div>
        <div style="font-size:0.75rem;color:var(--text3)">冲一冲</div>
      </div>
      <div style="flex:1;text-align:center;padding:0.5rem;border-left:1px solid var(--border);border-right:1px solid var(--border)">
        <div style="font-size:1.3rem;font-weight:800;color:var(--green)">${data.suggestions?.稳?.length || 0}</div>
        <div style="font-size:0.75rem;color:var(--text3)">稳一稳</div>
      </div>
      <div style="flex:1;text-align:center;padding:0.5rem">
        <div style="font-size:1.3rem;font-weight:800;color:var(--accent)">${data.suggestions?.保?.length || 0}</div>
        <div style="font-size:0.75rem;color:var(--text3)">保一保</div>
      </div>
    </div>`;

  groups.forEach(g => {
    const unis = data.suggestions?.[g.key] || [];
    if (!unis.length) return;
    html += `
      <h4 style="color:${g.color};margin:1.2rem 0 0.8rem">${g.label}</h4>
      ${unis.map((u, i) => `
        <div class="report-uni-card" style="animation:cardFade 0.35s ease ${i*80}ms both">
          <div class="report-uni-rank">#${i + 1}</div>
          <div class="report-uni-info">
            <div class="report-uni-name">${escapeHtml(u.cn)} <small style="color:var(--text3)">${escapeHtml(u.level)}</small></div>
            <div class="report-uni-meta">📍 ${escapeHtml(u.loc)} · 分数线 ${u.gaokao_score}分 · 就业率 ${u.employment_rate}% · 平均月薪 ¥${((u.avg_salary||0)/1000).toFixed(1)}k</div>
          </div>
          <button class="btn btn-ghost btn-sm" onclick="navigate('uni-detail',{id:${u.id}})">详情</button>
        </div>`).join('')}
      `;
  });

  html += `</div>
  <div class="tips-card" style="animation:cardFade 0.5s ease 0.3s both">
    <h4>💡 选校建议</h4>
    <ul style="margin:0;padding-left:1.2rem">${(data.tips || []).map(t => `<li>${escapeHtml(t)}</li>`).join('')}</ul>
  </div>`;

  el.innerHTML = html;
}

// ── 收藏 ──
async function loadFavorites() {
  const favs = JSON.parse(localStorage.getItem('unipulse_favs') || '[]');
  const grid = document.getElementById('favGrid');
  const empty = document.getElementById('favEmpty');
  if (!favs.length) {
    grid.innerHTML = '';
    const d = document.createElement('div');
    d.className = 'empty-state';
    d.id = 'favEmpty';
    d.innerHTML = '<div class="empty-icon">⭐</div><h3>暂无收藏</h3><p>浏览高校时点击⭐收藏，方便对比</p><button class="btn btn-primary" data-page="universities">去浏览高校</button>';
    grid.appendChild(d);
    return;
  }
  try {
    const ids = favs.join(',');
    const data = await apiGet(`/universities?limit=${favs.length}`);
    const favUnis = (data.data || []).filter(u => favs.includes(u.id));
    grid.innerHTML = favUnis.map(renderUniCard).join('');
    if (!favUnis.length) {
      const d = document.createElement('div');
      d.className = 'empty-state';
      d.id = 'favEmpty';
      d.innerHTML = '<div class="empty-icon">⭐</div><h3>暂无收藏</h3><p>浏览高校时点击⭐收藏，方便对比</p><button class="btn btn-primary" data-page="universities">去浏览高校</button>';
      grid.innerHTML = '';
      grid.appendChild(d);
    }
    animateCards(grid);
    attachFavBtns();
  } catch(e) { console.error(e); }
}

// ── 搜索 ──
document.getElementById('searchBtn')?.addEventListener('click', () => {
  const q = document.getElementById('searchInput')?.value?.trim();
  if (q) navigate('search', { q });
});
document.getElementById('searchInput')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    const q = e.target.value?.trim();
    if (q) navigate('search', { q });
  }
});

async function performSearch(q) {
  if (!q) return;
  document.getElementById('searchQueryDisplay').textContent = `"${escapeHtml(q)}" 的搜索结果`;
  document.getElementById('searchResults').innerHTML = Array(4).fill(skeletonUniCard()).join('');
  try {
    const data = await apiGet(`/search?q=${encodeURIComponent(q)}`);
    const uniHtml = data.universities?.length ? `<h3 style="margin:1.5rem 0 1rem">🏫 高校 (${data.universities.length})</h3><div class="uni-grid">${data.universities.map(renderUniCard).join('')}</div>` : '';
    const progHtml = data.programs?.length ? `<h3 style="margin:1.5rem 0 1rem">📚 专业 (${data.programs.length})</h3><div class="program-grid">${data.programs.map(p => `<div class="program-card" data-page="program-detail" data-name="${escapeHtml(p.name)}"><div class="program-icon">${escapeHtml(p.icon || '📚')}</div><div class="program-name">${escapeHtml(p.name)}</div></div>`).join('')}</div>` : '';
    const postHtml = data.posts?.length ? `<h3 style="margin:1.5rem 0 1rem">💬 论坛帖子 (${data.posts.length})</h3>${data.posts.map(p => `<div class="forum-post-card" data-page="post-detail" data-id="${p.id}"><div class="forum-post-title">${escapeHtml(p.title)}</div><div class="forum-post-meta"><span>🏷️ ${escapeHtml(p.category)}</span><span>👁️ ${p.views}</span><span>❤️ ${p.likes}</span></div></div>`).join('')}` : '';
    const resultsEl = document.getElementById('searchResults');
    resultsEl.innerHTML = uniHtml + progHtml + postHtml || '<div class="empty-state"><p>未找到相关内容</p></div>';
    if (data.universities?.length) animateCards(resultsEl.querySelector('.uni-grid') || resultsEl);
    attachFavBtns();
  } catch(e) {
    document.getElementById('searchResults').innerHTML = '<p style="color:var(--red);text-align:center;padding:2rem">搜索失败</p>';
  }
}

// ── 筛选事件 ──
document.getElementById('uniSearch')?.addEventListener('input', debounce(() => loadUniversities(1), 400));
document.getElementById('filterRegion')?.addEventListener('change', () => loadUniversities(1));
document.getElementById('filterLevel')?.addEventListener('change', () => loadUniversities(1));
document.getElementById('filterType')?.addEventListener('change', () => loadUniversities(1));
document.getElementById('sortUni')?.addEventListener('change', () => loadUniversities(1));
document.getElementById('clearFilters')?.addEventListener('click', () => {
  const ids = ['uniSearch','filterRegion','filterLevel','filterType'];
  ids.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  document.getElementById('sortUni').value = 'rank-asc';
  loadUniversities(1);
});
document.getElementById('forumSort')?.addEventListener('change', () => loadForum(1));
document.getElementById('forumCategory')?.addEventListener('change', () => loadForum(1));

// ── 防抖 ──
function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// ── 移动端菜单 ──
document.getElementById('mobileToggle')?.addEventListener('click', () => {
  document.getElementById('mobileMenu').classList.toggle('active');
});

// ── 卡片渐入动画 ──
const styleEl = document.createElement('style');
styleEl.textContent = `
@keyframes cardFade {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}
`;
document.head.appendChild(styleEl);

// ── 初始化 ──
loadHome();
fetch(API + '/track', {method:'POST', body: JSON.stringify({path: location.pathname})}).catch(() => {});
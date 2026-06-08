/* UniPulse v3 — 前端交互逻辑 */
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
  window.scrollTo(0, 0);
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

// ── API 工具 ──
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
  setTimeout(() => t.remove(), 3000);
}

// ── 工具函数 ──
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
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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
    showToast('已取消收藏');
  } else {
    favs.push(uniId);
    btn.textContent = '⭐ 已收藏';
    showToast('已收藏高校');
  }
  localStorage.setItem('unipulse_favs', JSON.stringify(favs));
}

function isFaved(uniId) {
  const favs = JSON.parse(localStorage.getItem('unipulse_favs') || '[]');
  return favs.includes(uniId);
}

// ── 通用卡片渲染 ──
function renderUniCard(u) {
  const stars = u.stars || 4;
  const starsHtml = '★'.repeat(Math.floor(stars)) + '☆'.repeat(5 - Math.floor(stars));
  const tagsHtml = (u.tags || []).slice(0, 3).map(t => `<span class="tag ${tagClass(t.type || 'blue')}">${escapeHtml(t.text)}</span>`).join('');
  const favBtn = isFaved(u.id) ? '⭐ 已收藏' : '⭐ 收藏';
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
        <button class="btn btn-ghost btn-sm fav-btn" data-uni="${u.id}">${favBtn}</button>
      </div>
    </div>`;
}

// ── 首页 ──
async function loadHome() {
  try {
    const [stats, hot, progs, posts] = await Promise.all([
      apiGet('/stats'),
      apiGet('/universities?sort=rank&order=asc&limit=6'),
      apiGet('/programs'),
      apiGet('/forum/posts?sort=hot&limit=5')
    ]);
    // Stats
    document.getElementById('heroStats').innerHTML = `
      <div class="stat-pill">🏫 ${stats.universities} 所高校</div>
      <div class="stat-pill">💼 ${stats.employment_records} 条就业数据</div>
      <div class="stat-pill">📈 平均月薪 ¥${(stats.avg_salary/1000).toFixed(1)}k</div>
      <div class="stat-pill">📖 ${stats.avg_employment_rate}% 就业率</div>`;
    // Hot universities
    document.getElementById('hotUnis').innerHTML = (hot.data || []).map(renderUniCard).join('');
    // Programs
    document.getElementById('programGrid').innerHTML = (progs || []).slice(0, 10).map(p => `
      <div class="program-card" data-page="program-detail" data-name="${escapeHtml(p.name)}">
        <div class="program-icon">${escapeHtml(p.icon || '📚')}</div>
        <div class="program-name">${escapeHtml(p.name)}</div>
        <div class="program-count">${p.count} 所高校</div>
      </div>`).join('');
    // Forum preview
    document.getElementById('forumPreview').innerHTML = (posts.data || []).map(p => `
      <div class="forum-post-card" data-page="post-detail" data-id="${p.id}">
        <div class="forum-post-title">${escapeHtml(p.title)}</div>
        <div class="forum-post-meta">
          <span>👤 ${escapeHtml(p.author)}</span>
          <span>🏷️ ${escapeHtml(p.category)}</span>
          <span>👁️ ${p.views} 浏览</span>
          <span>❤️ ${p.likes} 赞</span>
        </div>
      </div>`).join('');
    attachFavBtns();
  } catch(e) { console.error(e); }
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
  try {
    const data = await apiGet(`/universities?q=${encodeURIComponent(q)}&region=${region}&level=${level}&type=${type}&sort=${sort}&order=${order}&limit=20&offset=${offset}`);
    const total = data.total || 0;
    document.getElementById('uniResultsInfo').textContent = `共 ${total} 所高校，第 ${page} 页`;
    document.getElementById('uniGrid').innerHTML = (data.data || []).map(renderUniCard).join('');
    // Pagination
    const totalPages = Math.ceil(total / 20);
    const pagEl = document.getElementById('uniPagination');
    if (totalPages > 1) {
      let pages = [];
      for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || Math.abs(i - page) <= 2) pages.push(i);
        else if (pages[pages.length - 1] !== '...') pages.push('...');
      }
      pagEl.innerHTML = pages.map(p => p === '...' ? `<span class="btn btn-ghost btn-sm">...</span>` :
        `<button class="btn btn-sm ${p === page ? 'btn-primary' : 'btn-ghost'}" onclick="loadUniversities(${p})">${p}</button>`
      ).join('');
    } else { pagEl.innerHTML = ''; }
    attachFavBtns();
  } catch(e) { console.error(e); }
}

function attachFavBtns() {
  document.querySelectorAll('.fav-btn').forEach(btn => {
    btn.onclick = e => {
      e.stopPropagation();
      const uniId = parseInt(btn.dataset.uni);
      toggleFav(uniId, btn);
    };
  });
}

// ── 高校详情 ──
async function loadUniDetail(id) {
  document.getElementById('uniDetailContent').innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>加载中...</p></div>';
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
        <button class="btn ${isFaved(u.id) ? 'btn-primary' : 'btn-ghost'} fav-btn" data-uni="${u.id}">${favBtn}</button>
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
      <h3 style="margin:1.5rem 0 1rem">📊 六维能力图</h3>
      <div class="metrics-grid" style="grid-template-columns:repeat(3,1fr)">
        ${Object.entries(u.metrics || {}).map(([k, v]) => `<div class="metric-card">
          <div class="val">${typeof v === 'number' ? v + '%' : '—'}</div>
          <div class="lbl">${escapeHtml(k)}</div>
          <div class="progress-bar"><div class="progress-fill" style="width:${typeof v === 'number' ? v + '%' : '0'}"></div></div>
        </div>`).join('')}
      </div>
      ${u.programs?.length ? `
      <h3 style="margin:1.5rem 0 1rem">💼 各专业就业数据</h3>
      <table class="emp-table">
        <thead><tr><th>专业</th><th>平均月薪</th><th>起步月薪</th><th>就业率</th><th>前景评分</th></tr></thead>
        <tbody>${progHtml}</tbody>
      </table>` : ''}
      <h3 style="margin:1.5rem 0 1rem">🔗 相关专业</h3>
      <div class="uni-tags">${progCatsHtml}</div>`;
    attachFavBtns();
  } catch(e) {
    document.getElementById('uniDetailContent').innerHTML = `<p style="color:var(--red)">加载失败: ${e.message}</p>`;
  }
}

// ── 专业列表 ──
async function loadProgramsFull() {
  try {
    const progs = await apiGet('/programs');
    document.getElementById('programGridFull').innerHTML = (progs || []).map(p => `
      <div class="program-card" data-page="program-detail" data-name="${escapeHtml(p.name)}">
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
      return `<div class="uni-card" style="margin-bottom:1rem">
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
  try {
    const data = await apiGet(`/forum/posts?sort=${sort}&category=${category}&limit=20&offset=${offset}`);
    const total = data.total || 0;
    document.getElementById('forumPosts').innerHTML = (data.data || []).map(p => `
      <div class="forum-post-card" data-page="post-detail" data-id="${p.id}">
        <div class="forum-post-title">${escapeHtml(p.title)}</div>
        <div class="forum-post-excerpt">${escapeHtml(p.content?.slice(0, 200))}</div>
        <div class="forum-post-meta">
          <span>👤 ${escapeHtml(p.author)}</span>
          <span>🏷️ ${escapeHtml(p.category)}</span>
          <span>👁️ ${p.views} 浏览</span>
          <span>❤️ ${p.likes} 赞</span>
          <span>💬 ${p.comment_count || 0} 评论</span>
          <span>${relativeTime(p.created_at)}</span>
        </div>
        <div class="uni-tags" style="margin-top:0.5rem">
          ${(p.tags || []).map(t => `<span class="tag tag-blue">${escapeHtml(t)}</span>`).join('')}
        </div>
      </div>`).join('') || '<div class="empty-state"><p>暂无帖子</p></div>';
    // Tag cloud
    const allTags = (data.data || []).flatMap(p => p.tags || []);
    const tagCounts = {};
    allTags.forEach(t => tagCounts[t] = (tagCounts[t] || 0) + 1);
    document.getElementById('tagCloud').innerHTML = Object.entries(tagCounts).slice(0, 20).map(([t, c]) =>
      `<span class="tag tag-blue">${escapeHtml(t)} (${c})</span>`
    ).join('');
    // Pagination
    const totalPages = Math.ceil(total / 20);
    const pagEl = document.getElementById('forumPagination');
    if (totalPages > 1) {
      pagEl.innerHTML = Array.from({length: Math.min(totalPages, 10)}, (_, i) => {
        const p = i + 1;
        return `<button class="btn btn-sm ${p === page ? 'btn-primary' : 'btn-ghost'}" onclick="loadForum(${p})">${p}</button>`;
      }).join('');
    } else { pagEl.innerHTML = ''; }
  } catch(e) { console.error(e); }
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
        <button class="btn btn-ghost btn-sm" onclick="likePost(${p.id})">❤️ 赞一下 (${p.likes})</button>
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
    if (!title || !content) return;
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
  const btn = e?.target?.querySelector('button[type=submit]') || document.querySelector('#aiReportForm button[type=submit]');
  if (btn) { btn.disabled = true; btn.textContent = 'AI分析中...'; }
  try {
    const data = await apiGet(`/ai-report?score=${score}&province=${encodeURIComponent(province)}&interests=${encodeURIComponent(interests)}&subjects=${encodeURIComponent(subjects)}&preference=${encodeURIComponent(preference)}`);
    renderAiReport(data);
  } catch(e) {
    showToast('报告生成失败: ' + e.message, 'error');
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
    { label:'🛡️ 保一保（分数线低于你的分数）', key:'保', color:'var(--accent2)' },
  ];
  el.innerHTML = `
    <div class="report-section">
      <h3>📊 选校报告 — ${data.score}分 · ${data.province} · ${data.preference}</h3>
      ${groups.map(g => {
    const unis = data.suggestions?.[g.key] || [];
    if (!unis.length) return '';
    return `
        <h4 style="color:${g.color};margin:1.2rem 0 0.8rem">${g.label}</h4>
        ${unis.map((u, i) => `
          <div class="report-uni-card">
            <div class="report-uni-rank">#${i + 1}</div>
            <div class="report-uni-info">
              <div class="report-uni-name">${escapeHtml(u.cn)} <small style="color:var(--text3)">${escapeHtml(u.level)}</small></div>
              <div class="report-uni-meta">📍 ${escapeHtml(u.loc)} · 分数线 ${u.gaokao_score}分 · 就业率 ${u.employment_rate}% · 平均月薪 ¥${((u.avg_salary||0)/1000).toFixed(1)}k</div>
            </div>
            <button class="btn btn-sm btn-ghost" onclick="navigate('uni-detail',{id:${u.id}})">详情</button>
          </div>`).join('')}
        `}).join('')}
    </div>
    <div class="tips-card">
      <h4>💡 选校建议</h4>
      <ul class="tips-card">${(data.tips || []).map(t => `<li>${escapeHtml(t)}</li>`).join('')}</ul>
    </div>`;
}

// ── 收藏 ──
async function loadFavorites() {
  const favs = JSON.parse(localStorage.getItem('unipulse_favs') || '[]');
  const grid = document.getElementById('favGrid');
  const empty = document.getElementById('favEmpty');
  if (!favs.length) {
    grid.innerHTML = ''; grid.appendChild(empty || createEmptyState());
    return;
  }
  try {
    const ids = favs.join(',');
    const data = await apiGet(`/universities?limit=${favs.length}`);
    const favUnis = (data.data || []).filter(u => favs.includes(u.id));
    grid.innerHTML = favUnis.map(renderUniCard).join('');
    attachFavBtns();
  } catch(e) { console.error(e); }
}

function createEmptyState() {
  const d = document.createElement('div');
  d.className = 'empty-state'; d.id = 'favEmpty';
  d.innerHTML = '<div class="empty-icon">⭐</div><h3>暂无收藏</h3><p>浏览高校时点击⭐收藏，方便对比</p><button class="btn btn-primary" data-page="universities">去浏览高校</button>';
  return d;
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
  try {
    const data = await apiGet(`/search?q=${encodeURIComponent(q)}`);
    const uniHtml = data.universities?.length ? `<h3 style="margin:1.5rem 0 1rem">🏫 高校 (${data.universities.length})</h3><div class="uni-grid">${data.universities.map(renderUniCard).join('')}</div>` : '';
    const progHtml = data.programs?.length ? `<h3 style="margin:1.5rem 0 1rem">📚 专业 (${data.programs.length})</h3><div class="program-grid">${data.programs.map(p => `<div class="program-card" data-page="program-detail" data-name="${escapeHtml(p.name)}"><div class="program-icon">${escapeHtml(p.icon || '📚')}</div><div class="program-name">${escapeHtml(p.name)}</div></div>`).join('')}</div>` : '';
    const postHtml = data.posts?.length ? `<h3 style="margin:1.5rem 0 1rem">💬 论坛帖子 (${data.posts.length})</h3>${data.posts.map(p => `<div class="forum-post-card" data-page="post-detail" data-id="${p.id}"><div class="forum-post-title">${escapeHtml(p.title)}</div><div class="forum-post-meta"><span>🏷️ ${escapeHtml(p.category)}</span><span>👁️ ${p.views}</span><span>❤️ ${p.likes}</span></div></div>`).join('')}` : '';
    document.getElementById('searchResults').innerHTML = uniHtml + progHtml + postHtml || '<div class="empty-state"><p>未找到相关内容</p></div>';
    attachFavBtns();
  } catch(e) { console.error(e); }
}

// ── 筛选事件 ──
document.getElementById('uniSearch')?.addEventListener('input', () => loadUniversities(1));
document.getElementById('filterRegion')?.addEventListener('change', () => loadUniversities(1));
document.getElementById('filterLevel')?.addEventListener('change', () => loadUniversities(1));
document.getElementById('filterType')?.addEventListener('change', () => loadUniversities(1));
document.getElementById('sortUni')?.addEventListener('change', () => loadUniversities(1));
document.getElementById('clearFilters')?.addEventListener('click', () => {
  ['uniSearch','filterRegion','filterLevel','filterType'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = id === 'uniSearch' ? '' : '';
  });
  document.getElementById('sortUni').value = 'rank-asc';
  loadUniversities(1);
});
document.getElementById('forumSort')?.addEventListener('change', () => loadForum(1));
document.getElementById('forumCategory')?.addEventListener('change', () => loadForum(1));

// ── 移动端菜单 ──
document.getElementById('mobileToggle')?.addEventListener('click', () => {
  document.getElementById('mobileMenu').classList.toggle('active');
});

// ── 初始化 ──
loadHome();
// 追踪
fetch(API + '/track', {method:'POST', body: JSON.stringify({path: location.pathname})}).catch(()=>{});
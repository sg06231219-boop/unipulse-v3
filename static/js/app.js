/* UniPulse —高考志愿填报神器· 前端逻辑 */
const API = '/api';
let sessionId = localStorage.getItem('unipulse_session') || (() => {
  const id = 'sess_' + Math.random().toString(36).slice(2,10);
  localStorage.setItem('unipulse_session', id);
  return id;
})();
let currentPage = 'home';
let currentUniPage = 1;
let currentForumPage = 1;
let userScore = parseInt(localStorage.getItem('unipulse_score')) || 0;
let compareList = JSON.parse(localStorage.getItem('unipulse_compare') || '[]');
let wishList = JSON.parse(localStorage.getItem('unipulse_wish') || '[]'); // [{id, name, score, group}]
let browseMode = localStorage.getItem('unipulse_browse_mode') || 'university'; // 'university' | 'major'
let chanceFilter = ''; // '冲' | '稳' | '保' | ''

// ── 路由 ──
function navigate(page, params = {}) {
  document.querySelectorAll('.page').forEach(p => { p.classList.remove('active'); p.classList.add('hidden'); });
  document.querySelectorAll('.nav-link').forEach(n => n.classList.remove('active'));
  const el = document.getElementById('page-' + page);
  if (el) { el.classList.add('active'); el.classList.remove('hidden'); }
  const nav = document.querySelector(`.nav-link[data-page="${page}"]`);
  if (nav) nav.classList.add('active');
  currentPage = page;
  window.scrollTo({top:0,behavior:'smooth'});
  if (page === 'home') loadHome();
  else if (page === 'universities') loadUniversities(1);
  else if (page === 'uni-detail') loadUniDetail(params.id);
  else if (page === 'programs') loadProgramsFull();
  else if (page === 'program-detail') loadProgramDetail(params.name);
  else if (page === 'compare') loadCompare();
  else if (page === 'forum') loadForum(1);
  else if (page === 'post-detail') loadPostDetail(params.id);
  else if (page === 'favorites') loadFavorites();
  else if (page === 'wish-table') loadWishTable();
  else if (page === 'major-browse') loadMajorBrowse();
  else if (page === 'new-post') initNewPostPage();
  else if (page === 'search') performSearch(params.q || '');
}

document.addEventListener('click', e => {
  const link = e.target.closest('[data-page]');
  if (link) { e.preventDefault(); navigate(link.dataset.page, {id:link.dataset.id, name:link.dataset.name}); }
});

// ── API ──
async function apiGet(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}
async function apiPost(path, body) {
  const r = await fetch(API + path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}

// ── 工具 ──
function toast(msg) {
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = 'toast'; t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}
function $(id) { return document.getElementById(id); }
function getLevelClass(level) {
  if (level.includes('985')) return 'level-985';
  if (level.includes('211')) return 'level-211';
  if (level.includes('双一流')) return 'level-dy';
  return 'level-other';
}
function getChanceInfo(gap) {
  if (gap >= 30) return {text:'稳上', cls:'chance-bao', group:'保'};
  if (gap >= 20) return {text:'较稳', cls:'chance-bao', group:'保'};
  if (gap >= 10) return {text:'有把握', cls:'chance-wen', group:'稳'};
  if (gap >= 0) return {text:'可冲', cls:'chance-wen', group:'稳'};
  if (gap >= -10) return {text:'有风险', cls:'chance-chong', group:'冲'};
  if (gap >= -20) return {text:'较难', cls:'chance-chong', group:'冲'};
  if (gap >= -30) return {text:'困难', cls:'chance-none', group:'冲'};
  return {text:'差距大', cls:'chance-none', group:''};
}
function formatSalary(v) { return v >= 10000 ? (v/1000).toFixed(0)+'K' : v; }
function tagType(t) {
  const map = {'985':'gold','211':'blue','双一流':'cyan','985/211':'gold','独立学院':'orange','省属重点':'green','外语顶尖':'purple','传媒顶尖':'red','法学顶尖':'gold','药学顶尖':'red','电子信息':'cyan','两电一邮':'blue','外交官摇篮':'gold','经贸顶尖':'gold','政法黄埔':'red','外语':'purple','师范':'cyan','医学':'red','财经':'purple','建筑':'orange','农林':'green','理工':'blue','综合':'cyan'};
  for (const [k,v] of Object.entries(map)) { if (t.includes(k)) return v; }
  return 'blue';
}

// ── 首页 ──
async function loadHome() {
  loadHotUnis();
  loadPrograms();
  loadForumPreview();
  loadScoreDistribution();
  loadHeroStats();
}

async function loadHeroStats() {
  try {
    const s = await apiGet('/stats');
    $('heroStats').innerHTML = `
      <div class="stat-pill">🏫 <strong>${s.universities}</strong>所高校</div>
      <div class="stat-pill">💼 <strong>${s.employment_records}</strong>条就业数据</div>
      <div class="stat-pill">💰 平均起薪 <strong>${(s.avg_salary/1000).toFixed(0)}K</strong></div>
      <div class="stat-pill">📊 平均就业率 <strong>${s.avg_employment_rate}%</strong></div>
      <div class="stat-pill">985 <strong>${s.levels['985']}</strong>所 · 211 <strong>${s.levels['211']}</strong>所</div>
    `;
  } catch(e) {}
}

async function loadScoreDistribution() {
  try {
    const data = await apiGet('/score-distribution');
    const maxCount = Math.max(...data.map(d => d.count), 1);
    $('scoreDistChart').innerHTML = data.map(d => {
      const h = Math.max((d.count / maxCount) * 140, 4);
      const isMine = userScore && parseInt(d.range.split('-')[0]) <= userScore && parseInt(d.range.split('-')[1]) >= userScore;
      return `<div class="score-dist-bar" onclick="navigate('universities');$('scoreSlider').value=${parseInt(d.range.split('-')[0])};$('scoreDisplay').textContent='${d.range.split('-')[0]}分;filterByScore(${parseInt(d.range.split('-')[0])})">
        <div class="bar-count">${d.count}</div>
        <div class="bar" style="height:${h}px;${isMine?'background:linear-gradient(180deg,var(--green),rgba(0,214,143,0.3));box-shadow:0 0 12px rgba(0,214,143,0.3)':''}"></div>
        <div class="bar-label">${d.range}</div>
      </div>`;
    }).join('');
  } catch(e) {}
}

async function loadHotUnis() {
  try {
    const r = await apiGet('/universities?sort=rank&order=asc&limit=8');
    $('hotUnis').innerHTML = r.data.map(u => renderUniCard(u)).join('');
  } catch(e) {}
}

async function loadPrograms() {
  try {
    const p = await apiGet('/programs');
    const html = p.slice(0,8).map(pr => `
      <div class="program-card" data-page="program-detail" data-name="${encodeURIComponent(pr.name)}">
        <div class="prog-icon">${pr.icon}</div>
        <div class="prog-name">${pr.name}</div>
        <div class="prog-count">${pr.count}所高校</div>
      </div>`).join('');
    $('programGrid').innerHTML = html;
  } catch(e) {}
}

async function loadForumPreview() {
  try {
    const r = await apiGet('/forum/posts?sort=hot&limit=3');
    $('forumPreview').innerHTML = r.data.map(p => renderPostCard(p)).join('');
  } catch(e) {}
}

// ── 高校卡片渲染 ──
function renderUniCard(u, showChance = false) {
  const gap = userScore ? userScore - u.gaokao_score : null;
  const chance = gap !== null ? getChanceInfo(gap) : null;
  const isFav = false;
  const isInWish = wishList.some(w => w.id === u.id);
  return `<div class="uni-card" data-page="uni-detail" data-id="${u.id}">
    <button class="uni-card-fav ${isFav?'active':''}" onclick="event.stopPropagation();toggleFav(${u.id},this)">⭐</button>
    ${chance ? `<div class="uni-card-chance-badge ${chance.cls}">${chance.text}</div>` : ''}
    <div class="uni-card-header">
      <div class="uni-card-name">${esc(u.name)}</div>
      <span class="uni-card-level ${getLevelClass(u.level)}">${u.level.split('/')[0]}</span>
    </div>
    <div class="uni-card-meta">
      <span>📍${u.loc}</span><span>${u.type}</span><span>排名#${u.rank}</span>
    </div>
    <div class="uni-card-score">
      <span class="val">${u.gaokao_score}</span><span class="unit">分参考线</span>
    </div>
    ${chance ? `<div class="uni-card-chance ${chance.cls}">${userScore}分· ${chance.text}（差${Math.abs(gap)}分）</div>` : ''}
    <div class="uni-card-stats">
      <span class="uni-stat">就业率<strong>${u.employment_rate}%</strong></span>
      <span class="uni-stat">起薪 <strong>${formatSalary(u.avg_salary)}</strong></span>
      <span class="uni-stat">⭐${u.stars||'-'}</span>
    </div>
    <div class="uni-card-actions">
      <button class="btn btn-xs ${isInWish?'btn-primary':'btn-ghost'}" onclick="event.stopPropagation();addToWish(${u.id},'${esc(u.name)}',${u.gaokao_score})">${isInWish?'✓已加志愿':'+志愿表'}</button>
      <button class="btn btn-xs btn-ghost" onclick="event.stopPropagation();addToCompare(${u.id},'${esc(u.name)}',${u.gaokao_score})">⚖️</button>
    </div>
  </div>`;
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// ── 高校列表 ──
async function loadUniversities(page = 1) {
  currentUniPage = page;
  // Show skeleton
  if (typeof showUniGridSkeleton === 'function') showUniGridSkeleton();
  const q = $('uniSearch')?.value || '';
  const region = $('filterRegion')?.value || '';
  const level = $('filterLevel')?.value || '';
  const type_ = $('filterType')?.value || '';
  const sortVal = $('sortUni')?.value || 'rank-asc';
  const [sort, order] = sortVal.split('-');
  const params = new URLSearchParams({limit:20, offset:(page-1)*20, sort, order});
  if (q) params.set('q', q);
  if (region) params.set('region', region);
  if (level) params.set('level', level);
  if (type_) params.set('type', type_);
  try {
    const r = await apiGet('/universities?' + params);
    let data = r.data;
    // Client-side chance filter
    if (chanceFilter && userScore) {
      data = data.filter(u => {
        const gap = userScore - u.gaokao_score;
        const info = getChanceInfo(gap);
        return info.group === chanceFilter;
      });
    }
    $('uniResultsInfo').textContent = `共 ${chanceFilter && userScore ? data.length : r.total} 所高校`;
    $('uniGrid').innerHTML = data.map(u => renderUniCard(u, true)).join('');
    renderPagination('uniPagination', chanceFilter && userScore ? data.length : r.total, 20, page, p => loadUniversities(p));
  } catch(e) { toast('加载失败'); }
  hideUniGridSkeleton();
}

function filterByScore(score) {
  userScore = score;
  localStorage.setItem('unipulse_score', score);
  loadUniversities(1);
}

// ── 高校详情 ──
async function loadUniDetail(id) {
  try {
    const u = await apiGet('/universities/' + id);
    const gap = userScore ? userScore - u.gaokao_score : null;
    const chance = gap !== null ? getChanceInfo(gap) : null;
    const metrics = u.metrics || {};
    $('uniDetailContent').innerHTML = `
    <div class="uni-detail">
      <button class="btn btn-ghost btn-sm" onclick="navigate('universities')" style="margin-bottom:1rem">←返回高校列表</button>
      <div class="uni-detail-header">
        <div class="uni-detail-info">
          <h1>${esc(u.name)}</h1>
          <div style="color:var(--text3);font-size:0.9rem;margin-bottom:0.3rem">${esc(u.name)}</div>
          <div class="uni-detail-tags">
            ${(u.tags||[]).map(t => `<span class="tag tag-${tagType(t.text)}">${t.text}</span>`).join('')}
          </div>
          <p style="color:var(--text2);font-size:0.88rem;margin-top:0.8rem">${esc(u.description)}</p>
          ${chance ? `<div style="margin-top:1rem"><span class="uni-card-chance ${chance.cls}" style="font-size:0.9rem;padding:6px 16px">${userScore}分· ${chance.text}（差${Math.abs(gap)}分）</span></div>` : ''}
        </div>
        <div class="uni-detail-score-box">
          <div class="label">参考分数线</div>
          <div class="big">${u.gaokao_score}</div>
          <div class="label">排名 #${u.rank}</div>
          <div style="margin-top:0.8rem">
            <button class="btn btn-ghost btn-sm" onclick="addToCompare(${u.id},'${esc(u.name)}',${u.gaokao_score})">⚖️ 加入对比</button>
          </div>
        </div>
      </div>

      <div class="uni-detail-metrics">
        ${Object.entries(metrics).map(([k,v]) => `
          <div class="metric-card">
            <div class="metric-val" style="color:${v>=85?'var(--green)':v>=70?'var(--accent2)':'var(--yellow)'}">${v}</div>
            <div class="metric-label">${k}</div>
            <div class="metric-bar"><div class="metric-bar-fill ${v>=85?'fill-green':v>=70?'fill-accent':'fill-yellow'}" style="width:${v}%"></div></div>
          </div>`).join('')}
        <div class="metric-card">
          <div class="metric-val" style="color:var(--green)">${u.employment_rate}%</div>
          <div class="metric-label">就业率</div>
          <div class="metric-bar"><div class="metric-bar-fill fill-green" style="width:${u.employment_rate}%"></div></div>
        </div>
        <div class="metric-card">
          <div class="metric-val" style="color:var(--accent2)">${formatSalary(u.avg_salary)}</div>
          <div class="metric-label">平均起薪/月</div>
        </div>
        <div class="metric-card">
          <div class="metric-val" style="color:var(--yellow)">¥${u.tuition?.toLocaleString()}/年</div>
          <div class="metric-label">学费</div>
        </div>
      </div>

      ${u.programs && u.programs.length > 0 ? `
      <h2 style="font-size:1.2rem;font-weight:800;margin-bottom:0.8rem">💼 专业就业数据</h2>
      <div style="overflow-x:auto">
        <table class="emp-table">
          <thead><tr><th>专业</th><th>平均薪资</th><th>起薪</th><th>就业率</th><th>内卷指数</th><th>前景</th></tr></thead>
          <tbody>${u.programs.map(p => `<tr>
            <td><strong>${esc(p.program_name)}</strong></td>
            <td>${formatSalary(p.salary_avg)}</td>
            <td>${formatSalary(p.salary_entry)}</td>
            <td style="color:${p.employment_rate>=97?'var(--green)':'var(--text)'}">${p.employment_rate}%</td>
            <td style="color:${p.pressure>=75?'var(--red)':p.pressure>=60?'var(--yellow)':'var(--green)'}">${p.pressure}/100</td>
            <td style="color:${p.prospects>=85?'var(--green)':'var(--text)'}">${p.prospects}/100</td>
          </tr>`).join('')}</tbody>
        </table>
      </div>
      ${u.programs.map(p => p.description ? `<p style="font-size:0.82rem;color:var(--text3);margin-top:0.5rem"><strong>${esc(p.program_name)}</strong>：${esc(p.description)}</p>` : '').join('')}
      ` : ''}

      <!-- 详情页Tab切换 -->
      <div class="detail-tabs" style="margin-top:1.5rem">
        <button class="detail-tab active" onclick="switchDetailTab('overview',this)">📊 概况</button>
        <button class="detail-tab" onclick="switchDetailTab('province',this)">🗺️省分数线</button>
        <button class="detail-tab" onclick="switchDetailTab('employment',this)">💼 专业就业排行</button>
        <button class="detail-tab" onclick="switchDetailTab('info',this)">🏫 院校信息</button>
      </div>

      <!-- 概况Tab -->
      <div id="detailTabOverview" class="detail-tab-content active">
        ${u.programs && u.programs.length > 0 ? `
        <h2 style="font-size:1.2rem;font-weight:800;margin:1rem 0 0.8rem">💼 专业就业数据</h2>
        <div style="overflow-x:auto">
          <table class="emp-table">
            <thead><tr><th>专业</th><th>平均薪资</th><th>起薪</th><th>就业率</th><th>内卷指数</th><th>前景</th></tr></thead>
            <tbody>${u.programs.map(p => `<tr>
              <td><strong>${esc(p.program_name)}</strong></td>
              <td>${formatSalary(p.salary_avg)}</td>
              <td>${formatSalary(p.salary_entry)}</td>
              <td style="color:${p.employment_rate>=97?'var(--green)':'var(--text)'}">${p.employment_rate}%</td>
              <td style="color:${p.pressure>=75?'var(--red)':p.pressure>=60?'var(--yellow)':'var(--green)'}">${p.pressure}/100</td>
              <td style="color:${p.prospects>=85?'var(--green)':'var(--text)'}">${p.prospects}/100</td>
            </tr>`).join('')}</tbody>
          </table>
        </div>
        ` : '<p style="color:var(--text3);margin-top:1rem">暂无专业就业数据</p>'}
      </div>

      <!-- 省分数线Tab -->
      <div id="detailTabProvince" class="detail-tab-content" style="display:none">
        ${renderProvinceScores(u)}
        <div id="scoreTrendContainer" style="margin-top:1rem"></div>
      </div>

      <!-- 专业就业排行Tab -->
      <div id="detailTabEmployment" class="detail-tab-content" style="display:none">
        ${renderEmploymentRanking(u)}
      </div>

      <!-- 院校信息Tab -->
      <div id="detailTabInfo" class="detail-tab-content" style="display:none">
        ${renderUniInfo(u)}
      </div>
    </div>`;
  } catch(e) { toast('加载失败'); }
}

function switchDetailTab(tab, btn) {
  document.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.detail-tab-content').forEach(c => { c.style.display='none'; c.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  const el = document.getElementById('detailTab' + tab.charAt(0).toUpperCase() + tab.slice(1));
  if (el) { el.style.display='block'; el.classList.add('active'); }
  // Lazy load employment rankings when tab is opened
  if (tab === 'employment') {
    const uniId = el.closest('.uni-detail')?.querySelector('[data-uni-id]')?.dataset?.uniId;
    // Fallback: try to extract from the page URL or context
  }
  // Lazy load score trend when province tab is opened
  if (tab === 'province') {
    const trendEl = document.getElementById('scoreTrendContainer');
    if (trendEl && !trendEl.dataset.loaded) {
      trendEl.dataset.loaded = '1';
    }
  }
}

// ── 专业就业排行 ──
let _employmentRankingUniId = null;

function renderEmploymentRanking(u) {
  _employmentRankingUniId = u.id;
  const programs = u.programs || [];
  if (!programs.length) {
    return '<p style="color:var(--text3);margin-top:1rem">暂无专业就业数据</p>';
  }
  
  // Sort by salary by default
  const sorted = [...programs].sort((a, b) => (b.salary_avg || 0) - (a.salary_avg || 0));
  
  let html = '<div style="margin-top:1rem">';
  html += '<div class="prov-filter-bar" style="display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center;margin-bottom:0.8rem">';
  html += '<button class="prov-kele-btn active" data-sort="salary" onclick="sortEmploymentRanking(this,\'salary\')" style="padding:4px 12px;border-radius:6px;border:1px solid rgba(255,255,255,0.12);background:rgba(255,255,255,0.08);color:var(--text1);cursor:pointer;font-size:0.85rem">💰 按薪资</button>';
  html += '<button class="prov-kele-btn" data-sort="employment_rate" onclick="sortEmploymentRanking(this,\'employment_rate\')" style="padding:4px 12px;border-radius:6px;border:1px solid rgba(255,255,255,0.12);background:rgba(255,255,255,0.04);color:var(--text3);cursor:pointer;font-size:0.85rem">📊 按就业率</button>';
  html += '<button class="prov-kele-btn" data-sort="prospects" onclick="sortEmploymentRanking(this,\'prospects\')" style="padding:4px 12px;border-radius:6px;border:1px solid rgba(255,255,255,0.12);background:rgba(255,255,255,0.04);color:var(--text3);cursor:pointer;font-size:0.85rem">🚀 按前景</button>';
  html += '<span style="color:var(--text3);font-size:0.82rem;margin-left:auto">共' + sorted.length + '个专业</span>';
  html += '</div>';
  
  html += '<div id="employmentRankingBody">' + renderEmploymentRankingRows(sorted) + '</div>';
  html += '</div>';
  return html;
}

function renderEmploymentRankingRows(programs) {
  if (!programs.length) return '<p style="color:var(--text3)">暂无数据</p>';
  let html = '<div style="overflow-x:auto"><table class="emp-table"><thead><tr><th>排名</th><th>专业</th><th>平均薪资</th><th>起薪</th><th>就业率</th><th>内卷指数</th><th>前景</th></tr></thead><tbody>';
  programs.forEach((p, i) => {
    const rankBadge = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : (i + 1);
    html += '<tr>';
    html += '<td style="text-align:center;font-weight:700">' + rankBadge + '</td>';
    html += '<td><strong>' + esc(p.program_name) + '</strong></td>';
    html += '<td style="color:var(--accent2);font-weight:600">' + formatSalary(p.salary_avg) + '</td>';
    html += '<td>' + formatSalary(p.salary_entry) + '</td>';
    html += '<td style="color:' + (p.employment_rate >= 97 ? 'var(--green)' : 'var(--text)') + '">' + p.employment_rate + '%</td>';
    html += '<td style="color:' + (p.pressure >= 75 ? 'var(--red)' : p.pressure >= 60 ? 'var(--yellow)' : 'var(--green)') + '">' + p.pressure + '/100</td>';
    html += '<td style="color:' + (p.prospects >= 85 ? 'var(--green)' : 'var(--text)') + '">' + p.prospects + '/100</td>';
    html += '</tr>';
    if (p.description) {
      html += '<tr><td colspan="7" style="padding:0.3rem 1rem;font-size:0.82rem;color:var(--text3);background:rgba(255,255,255,0.02)">' + esc(p.description) + '</td></tr>';
    }
  });
  html += '</tbody></table></div>';
  return html;
}

function sortEmploymentRanking(btn, sortBy) {
  document.querySelectorAll('[data-sort]').forEach(b => {
    b.classList.remove('active');
    b.style.background = 'rgba(255,255,255,0.04)';
    b.style.color = 'var(--text3)';
  });
  btn.classList.add('active');
  btn.style.background = 'rgba(255,255,255,0.08)';
  btn.style.color = 'var(--text1)';
  
  if (!_employmentRankingUniId) return;
  const body = document.getElementById('employmentRankingBody');
  if (!body) return;
  
  // Get programs from the page data
  const tables = document.querySelectorAll('.emp-table');
  // Re-fetch data and sort
  apiGet('/employment?uni_id=' + _employmentRankingUniId + '&sort=' + sortBy + '&order=desc&limit=50').then(data => {
    body.innerHTML = renderEmploymentRankingRows(data);
  }).catch(() => toast('排序失败'));
}

function renderProvinceScores(u) {
  // Directly render from inline data with full major scores (no async needed)
  const ps = u.province_scores || {};
  const containerId = 'provScoresContainer';
  const firstVal = Object.values(ps)[0];
  const isDictFormat = firstVal && typeof firstVal === 'object' && !Array.isArray(firstVal);
  
  // Build base_scores and extract major_scores from inline data
  let baseScores = {};
  let majorScores = {};
  if (isDictFormat) {
    for (const [prov, info] of Object.entries(ps)) {
      if (info && info.min_score) {
        baseScores[prov] = info.min_score;
        if (info.majors && Array.isArray(info.majors) && info.majors.length > 0) {
          majorScores[prov] = info.majors;
        }
      }
    }
  } else {
    for (const [prov, score] of Object.entries(ps)) {
      if (typeof score === 'number') baseScores[prov] = score;
    }
  }
  
  const provinces = Object.keys(baseScores).sort();
  const totalMajors = Object.values(majorScores).reduce((a, b) => a + b.length, 0);
  
  if (provinces.length === 0) {
    return '<div id="' + containerId + '" style="margin-top:0.5rem"><p style="color:var(--text3)\">\u6682\u65e0\u7701\u5206\u6570\u7ebf\u6570\u636e</p></div>';
  }
  
  let html = '<div id="' + containerId + '" style="margin-top:0.5rem">';
  // Filter bar
  html += '<div class="prov-filter-bar" style="display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center;margin-bottom:0.8rem">';
  html += '<input id="provSearch" type="text" placeholder="\u641c\u7d22\u7701\u4efd..." style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:6px;padding:5px 10px;color:var(--text1);font-size:0.85rem;width:140px;outline:none" oninput="filterProvRows()">';
  html += '<select id="provTypeFilter" onchange="filterProvRows()" style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:6px;padding:5px 8px;color:var(--text1);font-size:0.85rem;outline:none"><option value="all">\u5168\u90e8\u79d1\u7c7b</option><option value="\u7efc\u5408">\u7efc\u5408</option><option value="\u7406\u79d1">\u7406\u79d1</option><option value="\u6587\u79d1">\u6587\u79d1</option></select>';
  html += '<select id="provSortBy" onchange="filterProvRows()" style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:6px;padding:5px 8px;color:var(--text1);font-size:0.85rem;outline:none"><option value="name">\u6309\u7701\u4efd</option><option value="score-asc">\u5206\u6570\u4f4e\u2192\u9ad8</option><option value="score-desc">\u5206\u6570\u9ad8\u2192\u4f4e</option>';
  if (userScore) html += '<option value="gap-desc">\u5dee\u8ddd\u5927\u2192\u5c0f</option>';
  html += '</select>';
  html += '<span id="provCount" style="color:var(--text3);font-size:0.82rem;margin-left:auto">' + provinces.length + '\u4e2a\u7701\u4efd\u00b7' + totalMajors + '\u6761\u4e13\u4e1a\u5206\u6570\u7ebf</span>';
  html += '</div>';
  // User score hint
  if (userScore) {
    html += '<p style="color:var(--text2);margin-bottom:0.6rem;font-size:0.85rem">\ud83d\udca1 \u4ee5\u4f60\u7684<strong>' + userScore + '\u5206</strong> \u4e3a\u57fa\u51c6\uff0c\u70b9\u51fb\u7701\u4efd\u5c55\u5f00\u4e13\u4e1a\u5206\u6570\u7ebf</p>';
  } else {
    html += '<p style="color:var(--text2);margin-bottom:0.6rem;font-size:0.85rem">\ud83d\udca1 \u5728\u9996\u9875\u8f93\u5165\u4f60\u7684\u5206\u6570\uff0c\u53ef\u67e5\u770b\u5404\u7701\u4efd\u5f55\u53d6\u6982\u7387 | \u70b9\u51fb\u7701\u4efd\u5c55\u5f00\u4e13\u4e1a\u5206\u6570\u7ebf</p>';
  }
  // Table
  html += '<div style="overflow-x:auto"><table class="emp-table" id="provTable"><thead><tr>';
  html += '<th style="width:28px"></th><th>\u7701\u4efd</th><th>\u6821\u7ebf</th><th>\u4e13\u4e1a\u6570</th><th>\u5e74\u4efd</th>';
  if (userScore) html += '<th>\u5dee\u8ddd</th><th>\u8bc4\u4f30</th>';
  html += '</tr></thead><tbody>';
  for (const prov of provinces) {
    const base = baseScores[prov];
    const gap = userScore ? userScore - base : null;
    const chance = gap !== null ? getChanceInfo(gap) : null;
    const info = isDictFormat ? ps[prov] : {};
    const year = info.year || 2025;
    const majors = majorScores[prov] || [];
    const hasMajors = majors.length > 0;
    const rowId = 'prov_' + prov.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, '');
    // \u7edf\u8ba1\u5404\u79d1\u7c7b\u4e13\u4e1a\u6570
    const keleCounts = {};
    majors.forEach(m => { const t = m.type || '综合'; keleCounts[t] = (keleCounts[t] || 0) + 1; });
    const keleSummary = Object.entries(keleCounts).map(([k, v]) => k + v).join(' ');
    
    html += '<tr class="prov-row" data-prov="' + esc(prov) + '" data-score="' + base + '" data-types="' + Object.keys(keleCounts).join(',') + '" style="cursor:pointer" onclick="toggleProvMajors(\'' + rowId + '\')">';
    html += '<td style="text-align:center">' + (hasMajors ? '\u25aa' : '') + '</td>';
    html += '<td>' + esc(prov) + '</td>';
    html += '<td><strong>' + base + '</strong></td>';
    html += '<td style="font-size:0.82rem;color:var(--text3)">' + majors.length + (keleSummary ? ' <span style="font-size:0.75rem">(' + keleSummary + ')</span>' : '') + '</td>';
    html += '<td style="font-size:0.78rem;color:var(--text3)">' + year + '</td>';
    if (userScore) {
      html += '<td style="color:' + (gap >= 0 ? 'var(--green)' : 'var(--red)') + '">' + (gap >= 0 ? '+' : '') + gap + '</td>';
      html += '<td><span class="uni-card-chance ' + (chance ? chance.cls : '') + '">' + (chance ? chance.text : '-') + '</span></td>';
    }
    html += '</tr>';
    // \u4e13\u4e1a\u8be6\u60c5\u884c\uff08\u9ed8\u8ba4\u6536\u8d77\uff09
    if (hasMajors) {
      html += '<tr id="' + rowId + '" class="prov-detail-row" style="display:none"><td colspan="' + (userScore ? 8 : 6) + '" style="padding:0">';
      html += '<div style="padding:0.6rem 0.8rem;background:rgba(255,255,255,0.02)">';
      // \u79d1\u7c7b\u6807\u7b7e\u5207\u6362
      const types = Object.keys(keleCounts);
      if (types.length > 1) {
        html += '<div style="display:flex;gap:0.4rem;margin-bottom:0.5rem">';
        html += '<button class="prov-kele-btn active" data-rowid="' + rowId + '" data-type="all" onclick="filterMajors(this,\'' + rowId + '\',\'all\')">\u5168\u90e8</button>';
        types.forEach(t => {
          html += '<button class="prov-kele-btn" data-rowid="' + rowId + '" data-type="' + t + '" onclick="filterMajors(this,\'' + rowId + '\',\'' + t + '\')">' + t + '(' + keleCounts[t] + ')</button>';
        });
        html += '</div>';
      }
      html += '<table class="emp-table prov-major-table" style="margin:0;font-size:0.82rem"><thead><tr><th>\u4e13\u4e1a\u540d\u79f0</th><th>\u79d1\u7c7b</th><th>\u9009\u79d1\u8981\u6c42</th><th>\u6700\u4f4e\u5206</th><th>\u6700\u4f4e\u4f4d\u6b21</th><th>\u5e74\u4efd</th>';
      if (userScore) html += '<th>\u5dee\u8ddd</th><th>\u8bc4\u4f30</th>';
      html += '</tr></thead><tbody>';
      for (const m of majors) {
        const mScore = m.min_score != null ? m.min_score : (m.score || 0);
        const mName = m.sp_name || m.major || '-';
        const mSubjectReq = m.subject_req || '-';
        const mRank = (m.min_rank != null && m.min_rank > 0) ? m.min_rank : '';
        const mYear = m.year || '';
        const mType = m.type || '综合';
        const mGap = userScore ? userScore - mScore : null;
        let chanceLabel = '-', chanceGroup = 'none';
        if (mGap !== null) {
          if (mGap > 20) { chanceLabel = '稳'; chanceGroup = 'wen'; }
          else if (mGap > 0) { chanceLabel = '冲'; chanceGroup = 'chong'; }
          else { chanceLabel = '保'; chanceGroup = 'bao'; }
        }
        html += '<tr class="major-row" data-type="' + esc(mType) + '">';
        html += '<td style="white-space:nowrap">' + esc(mName) + '</td>';
        html += '<td><span class="tag tag-' + (mType.includes('理') ? 'accent2' : mType.includes('文') ? 'warning' : 'info') + '" style="font-size:0.72rem;padding:1px 5px">' + esc(mType) + '</span></td>';
        html += '<td style="font-size:0.78rem;color:var(--text3)">' + esc(mSubjectReq) + '</td>';
        html += '<td><strong>' + mScore + '</strong></td>';
        html += '<td style="color:var(--text3)">' + mRank + '</td>';
        html += '<td style="color:var(--text3)">' + mYear + '</td>';
        if (userScore) {
          html += '<td style="color:' + (mGap >= 0 ? 'var(--green)' : 'var(--red)') + '">' + (mGap >= 0 ? '+' : '') + mGap + '</td>';
          html += '<td><span class="uni-card-chance chance-' + chanceGroup + '" style="font-size:0.72rem">' + chanceLabel + '</span></td>';
        }
        html += '</tr>';
      }
      html += '</tbody></table></div></td></tr>';
    }
  }
  html += '</tbody></table></div></div>';
  return html;
}

async function loadProvinceMajorScores(uniId, containerId, preloadedBaseScores) {
  const el = document.getElementById(containerId);
  if (!el) return;
  // If we already have base scores from inline data, just try to load major scores
  if (preloadedBaseScores && Object.keys(preloadedBaseScores).length > 0) {
    try {
      const data = await apiGet('/universities/' + uniId + '/province-scores');
      const majorScores = data.major_scores || {};
      if (Object.keys(majorScores).length > 0) {
        // TODO: enhance display with major scores if available
      }
    } catch(e) {}
    return; // Already rendered inline, no need to re-render
  }
  try {
    const data = await apiGet('/universities/' + uniId + '/province-scores');
    const baseScores = data.base_scores || {};
    const majorScores = data.major_scores || {};
    const provinces = Object.keys(baseScores).sort();
    if (provinces.length === 0) {
      el.innerHTML = '<p style="color:var(--text3)">暂无省分数线数据</p>';
      return;
    }

    // ── 筛选栏 ──
    let html = '<div class="prov-filter-bar" style="display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center;margin-bottom:0.8rem">';
    // 搜索框
    html += '<input id="provSearch" type="text" placeholder="搜索省份..." style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:6px;padding:5px 10px;color:var(--text1);font-size:0.85rem;width:140px;outline:none" oninput="filterProvRows()">';
    // 科类筛选
    html += '<select id="provTypeFilter" onchange="filterProvRows()" style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:6px;padding:5px 8px;color:var(--text1);font-size:0.85rem;outline:none">';
    html += '<option value="all">全部科类</option><option value="综合">综合</option><option value="理科">理科</option><option value="文科">文科</option>';
    html += '</select>';
    // 排序
    html += '<select id="provSortBy" onchange="filterProvRows()" style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:6px;padding:5px 8px;color:var(--text1);font-size:0.85rem;outline:none">';
    html += '<option value="name">按省份</option><option value="score-asc">分数低→高</option><option value="score-desc">分数高→低</option>';
    if (userScore) html += '<option value="gap-desc">差距大→小</option>';
    html += '</select>';
    // 统计
    html += '<span id="provCount" style="color:var(--text3);font-size:0.82rem;margin-left:auto">' + provinces.length + '个省份· ' + Object.values(majorScores).reduce((a, b) => a + b.length, 0) + '条专业分数线</span>';
    html += '</div>';

    // ── 用户分数提示 ──
    if (userScore) {
      html += '<p style="color:var(--text2);margin-bottom:0.6rem;font-size:0.85rem">💡 以你的<strong>' + userScore + '分</strong> 为基准，点击省份展开专业分数线</p>';
    } else {
      html += '<p style="color:var(--text2);margin-bottom:0.6rem;font-size:0.85rem">💡 在首页输入你的分数，可查看各省份录取概率 | 点击省份展开专业分数线</p>';
    }

    // ── 省份表格 ──
    html += '<div style="overflow-x:auto"><table class="emp-table" id="provTable"><thead><tr>';
    html += '<th style="width:28px"></th><th>省份</th><th>校线</th><th>专业数</th><th>年份</th>';
    if (userScore) html += '<th>差距</th><th>评估</th>';
    html += '</tr></thead><tbody>';

    for (const prov of provinces) {
      const base = baseScores[prov];
      const gap = userScore ? userScore - base : null;
      const chance = gap !== null ? getChanceInfo(gap) : null;
      const majors = majorScores[prov] || [];
      const hasMajors = majors.length > 0;
      const rowId = 'prov_' + prov.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, '');
      // 统计各科类专业数（兼容新旧格式）
      const keleCounts = {};
      majors.forEach(m => { const t = m.type || m.subject_group || '综合'; keleCounts[t] = (keleCounts[t] || 0) + 1; });
      const keleSummary = Object.entries(keleCounts).map(([k, v]) => k + v).join(' ');

      html += '<tr class="prov-row" data-prov="' + esc(prov) + '" data-score="' + base + '" data-gap="' + (gap || 0) + '" data-types="' + Object.keys(keleCounts).join(',') + '" style="cursor:pointer" onclick="toggleProvMajors(\'' + rowId + '\')">';
      html += '<td style="text-align:center">' + (hasMajors ? '▪' : '') + '</td>';
      html += '<td>' + esc(prov) + '</td>';
      html += '<td><strong>' + base + '</strong></td>';
      html += '<td style="font-size:0.82rem;color:var(--text3)">' + majors.length + ' <span style="font-size:0.75rem">(' + keleSummary + ')</span></td>';
      // 年份标签
      const years = [...new Set(majors.map(m => m.year).filter(Boolean))].sort().reverse();
      if (years.length) html += '<td style="font-size:0.78rem;color:var(--text3)">' + years.join('/') + '</td>';
      if (userScore) {
        html += '<td style="color:' + (gap >= 0 ? 'var(--green)' : 'var(--red)') + '">' + (gap >= 0 ? '+' : '') + gap + '</td>';
        html += '<td><span class="uni-card-chance ' + (chance ? chance.cls : '') + '">' + (chance ? chance.text : '-') + '</span></td>';
      }
      html += '</tr>';

      // 专业详情行（默认收起，
      if (hasMajors) {
        html += '<tr id="' + rowId + '" class="prov-detail-row" style="display:none"><td colspan="' + (userScore ? 8 : 6) + '" style="padding:0">';
        html += '<div style="padding:0.6rem 0.8rem;background:rgba(255,255,255,0.02)">';
        // 科类标签切换
        const types = Object.keys(keleCounts);
        if (types.length > 1) {
          html += '<div style="display:flex;gap:0.4rem;margin-bottom:0.5rem">';
          html += '<button class="prov-kele-btn active" data-rowid="' + rowId + '" data-type="all" onclick="filterMajors(this,\'' + rowId + '\',\'all\')">全部</button>';
          types.forEach(t => {
            html += '<button class="prov-kele-btn" data-rowid="' + rowId + '" data-type="' + t + '" onclick="filterMajors(this,\'' + rowId + '\',\'' + t + '\')">' + t + '(' + keleCounts[t] + ')</button>';
          });
          html += '</div>';
        }
        html += '<table class="emp-table prov-major-table" style="margin:0;font-size:0.82rem"><thead><tr><th>专业名称</th><th>科类</th><th>选科要求</th><th>最低分</th><th>最低位次</th><th>年份</th>';
        if (userScore) html += '<th>差距</th><th>评估</th>';
        html += '</tr></thead><tbody>';
        for (const m of majors) {
          const mScore = m.min_score != null ? m.min_score : m.score;
          const mName = m.sp_name || m.major || '-';
          const mSubjectGroup = m.subject_group || '';
          const mSubjectReq = m.subject_req || '';
          const mRank = (m.min_rank != null && m.min_rank > 0) ? m.min_rank : '';
          const mYear = m.year || '';
          const mType = m.type || m.subject_group || '综合';
          const mGap = userScore ? userScore - mScore : null;
          // 冲稳保分色：> score+20=稳蓝, > score=冲线, else=保综
          let chanceLabel, chanceColor, chanceGroup;
          if (mGap !== null) {
            if (mGap > 20) { chanceLabel = '稳'; chanceColor = 'var(--accent2)'; chanceGroup = 'wen'; }
            else if (mGap > 0) { chanceLabel = '冲'; chanceColor = 'var(--red)'; chanceGroup = 'chong'; }
            else { chanceLabel = '保'; chanceColor = 'var(--green)'; chanceGroup = 'bao'; }
          }
          html += '<tr class="major-row" data-type="' + esc(mType) + '">';
          html += '<td style="white-space:nowrap">' + esc(mName) + '</td>';
          html += '<td><span class="tag tag-' + (mType.includes('理') ? 'accent2' : mType.includes('文') ? 'warning' : 'info') + '" style="font-size:0.72rem;padding:1px 5px">' + esc(mType) + '</span></td>';
          html += '<td style="font-size:0.78rem;color:var(--text3)">' + (mSubjectReq ? esc(mSubjectReq) : '-') + '</td>';
          html += '<td><strong>' + mScore + '</strong></td>';
          html += '<td style="color:var(--text3)">' + mRank + '</td>';
          html += '<td style="color:var(--text3)">' + mYear + '</td>';
          if (userScore) {
            html += '<td style="color:' + (mGap >= 0 ? 'var(--green)' : 'var(--red)') + '">' + (mGap >= 0 ? '+' : '') + mGap + '</td>';
            html += '<td><span class="uni-card-chance chance-' + chanceGroup + '" style="font-size:0.72rem">' + chanceLabel + '</span></td>';
          }
          html += '</tr>';
        }
        html += '</tbody></table></div></td></tr>';
      }
    }

    html += '</tbody></table></div>';
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = '<p style="color:var(--text3)">加载失败: ' + esc(e.message) + '</p>';
  }
}

function toggleProvMajors(rowId) {
  const row = document.getElementById(rowId);
  if (!row) return;
  const isHidden = row.style.display === 'none' || !row.classList.contains('expanded');
  
  // Close all other expanded rows first (accordion behavior)
  document.querySelectorAll('.prov-detail-row.expanded').forEach(r => {
    if (r.id !== rowId) {
      r.style.display = 'none';
      r.classList.remove('expanded');
      const prevRow = r.previousElementSibling;
      if (prevRow) {
        prevRow.classList.remove('prov-expanded');
        const arrow = prevRow.querySelector('td:first-child');
        if (arrow) arrow.textContent = '\u25aa';
      }
    }
  });
  
  if (isHidden) {
    row.style.display = 'table-row';
    row.classList.add('expanded');
    const prevRow = row.previousElementSibling;
    if (prevRow) {
      prevRow.classList.add('prov-expanded');
      const arrow = prevRow.querySelector('td:first-child');
      if (arrow) arrow.textContent = '\u25bc';
    }
  } else {
    row.style.display = 'none';
    row.classList.remove('expanded');
    const prevRow = row.previousElementSibling;
    if (prevRow) {
      prevRow.classList.remove('prov-expanded');
      const arrow = prevRow.querySelector('td:first-child');
      if (arrow) arrow.textContent = '\u25aa';
    }
  }
}

function filterProvRows() {
  const search = (document.getElementById('provSearch')?.value || '').trim();
  const typeFilter = document.getElementById('provTypeFilter')?.value || 'all';
  const sortBy = document.getElementById('provSortBy')?.value || 'name';
  const rows = document.querySelectorAll('.prov-row');
  let visible = 0;
  const rowsData = [];
  rows.forEach(row => {
    const prov = row.dataset.prov;
    const types = (row.dataset.types || '').split(',');
    const matchSearch = !search || prov.includes(search);
    const matchType = typeFilter === 'all' || types.includes(typeFilter);
    const show = matchSearch && matchType;
    row.style.display = show ? '' : 'none';
    // Also hide/show detail row
    const detailRow = row.nextElementSibling;
    if (detailRow && detailRow.classList.contains('prov-detail-row')) {
      detailRow.style.display = show ? detailRow.style.display : 'none';
    }
    if (show) {
      visible++;
      rowsData.push({ el: row, prov: prov, score: parseInt(row.dataset.score), gap: parseInt(row.dataset.gap) });
    }
  });
  // Sort
  if (sortBy !== 'name') {
    const tbody = document.querySelector('#provTable tbody');
    rowsData.sort((a, b) => {
      if (sortBy === 'score-asc') return a.score - b.score;
      if (sortBy === 'score-desc') return b.score - a.score;
      if (sortBy === 'gap-desc') return b.gap - a.gap;
      return 0;
    });
    rowsData.forEach(item => {
      tbody.appendChild(item.el);
      const detail = item.el.nextElementSibling;
      if (detail && detail.classList.contains('prov-detail-row')) {
        tbody.appendChild(detail);
      }
    });
  }
  const countEl = document.getElementById('provCount');
  if (countEl) countEl.textContent = visible + '个省份';
}

function filterMajors(btn, rowId, type) {
  const container = document.getElementById(rowId);
  if (!container) return;
  // Toggle active button
  container.querySelectorAll('.prov-kele-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  // Filter rows
  container.querySelectorAll('.major-row').forEach(row => {
    row.style.display = (type === 'all' || row.dataset.type === type) ? '' : 'none';
  });
}
function renderUniInfo(u) {
  let html = '<div class="uni-info-grid">';
  const fields = [
    ['motto', '校训', '🎓'],
    ['founded_year', '建校年份', '📅'],
    ['campus_area', '校园面积', '📐'],
    ['student_count', '在校学生', '👥'],
    ['faculty_count', '专任教师', '👨‍🏫'],
    ['doctoral_programs', '博士点', '🎓'],
    ['master_programs', '硕士点', '📚'],
    ['national_key_programs', '国家重点学科', '⭐'],
    ['postdoc_stations', '博士后流动站', '🔬'],
    ['academicians', '院士人数', '🏅'],
    ['school_nature', '办学性质', '🏛️'],
    ['affiliation', '主管部门', '🏢'],
    ['dormitory', '宿舍条件', '🏠'],
    ['canteen', '食堂评价', '🍽️'],
    ['campus_life', '校园生活', '🌈'],
    ['notable_alumni', '知名校友', '🌟'],
    ['address', '地址', '📍'],
    ['phone', '联系电话', '📞'],
    ['website', '官方网站', '🔗'],
  ];
  fields.forEach(([key, label, icon]) => {
    const val = u[key];
    if (val && val !== '' && val !== 0) {
      if (key === 'website') {
        html += '<div class="info-item"><span class="info-label">' + icon + ' ' + label + '</span><span class="info-value"><a href="' + esc(String(val)) + '" target="_blank" rel="noopener" style="color:var(--accent2)">' + esc(String(val)) + '</a></span></div>';
      } else if (key === 'notable_alumni') {
        const alumni = Array.isArray(val) ? val.join('、') : String(val);
        html += '<div class="info-item"><span class="info-label">' + icon + ' ' + label + '</span><span class="info-value">' + esc(alumni) + '</span></div>';
      } else {
        html += '<div class="info-item"><span class="info-label">' + icon + ' ' + label + '</span><span class="info-value">' + esc(String(val)) + '</span></div>';
      }
    }
  });
  html += '</div>';
  const hasAny = fields.some(([key]) => u[key] && u[key] !== '' && u[key] !== 0);
  return hasAny ? html : '<p style="color:var(--text3)">暂无详细信息</p>';
}

// ── 院校对比 ──
function loadCompare() {
  renderCompareSlots();
  $('compareResult').classList.add('hidden');
}

function renderCompareSlots() {
  $('compareSlots').innerHTML = Array.from({length:5}, (_, i) => {
    const item = compareList[i];
    if (item) {
      return `<div class="compare-slot filled">
        <button class="slot-remove" onclick="removeCompare(${i})">✓</button>
        <div class="slot-name">${esc(item.name)}</div>
        <div class="slot-score">${item.score}分</div>
      </div>`;
    }
    return `<div class="compare-slot" onclick="pickForCompare(${i})">
      <div class="slot-placeholder">+ 添加院校</div>
    </div>`;
  }).join('');
  $('compareGoBtn').disabled = compareList.length < 2;
}

async function pickForCompare(slot) {
  const q = prompt('输入高校名称搜索');
  if (!q) return;
  try {
    const r = await apiGet('/universities?q=' + encodeURIComponent(q) + '&limit=8');
    if (r.data.length === 0) { toast('未找到'); return; }
    const choice = r.data.length === 1 ? r.data[0] : r.data.find(u => u.cn === q) || r.data[0];
    compareList[slot] = {id: choice.id, name: choice.name, score: choice.gaokao_score};
    localStorage.setItem('unipulse_compare', JSON.stringify(compareList));
    renderCompareSlots();
  } catch(e) { toast('搜索失败'); }
}

function removeCompare(idx) {
  compareList.splice(idx, 1);
  localStorage.setItem('unipulse_compare', JSON.stringify(compareList));
  renderCompareSlots();
}

function addToCompare(id, name, score) {
  if (compareList.length >= 5) { toast('最多对比5所'); return; }
  if (compareList.some(c => c.id === id)) { toast('已在对比中'); return; }
  compareList.push({id, name, score});
  localStorage.setItem('unipulse_compare', JSON.stringify(compareList));
  toast('已加入对比');
}

async function doCompare() {
  if (compareList.length < 2) return;
  try {
    const ids = compareList.map(c => c.id);
    const data = await apiPost('/compare', ids);
    renderCompareResult(data);
  } catch(e) { toast('对比失败'); }
}

function renderCompareResult(unis) {
  renderCompareResultV2(unis);
}

// ── 专业列表 ──
async function loadProgramsFull() {
  try {
    const p = await apiGet('/programs');
    $('programGridFull').innerHTML = p.map(pr => `
      <div class="program-card" data-page="program-detail" data-name="${encodeURIComponent(pr.name)}">
        <div class="prog-icon">${pr.icon}</div>
        <div class="prog-name">${pr.name}</div>
        <div class="prog-count">${pr.count}所高校</div>
      </div>`).join('');
  } catch(e) {}
}

async function loadProgramDetail(name) {
  try {
    const d = await apiGet('/programs/' + name);
    const unis = d.universities || [];
    const emp = d.employment || {};
    $('programDetailContent').innerHTML = `
      <button class="btn btn-ghost btn-sm" onclick="navigate('programs')" style="margin-bottom:1rem">←返回专业列表</button>
      <h1>${d.icon} ${esc(d.name)}</h1>
      <p style="color:var(--text2);margin:0.5rem 0 1rem">共 ${unis.length} 所高校开设此专业</p>
      <div class="uni-grid">${unis.slice(0,20).map(uniName => {
        const e = emp[uniName];
        if (e) {
          return `<div class="uni-card" data-page="uni-detail" data-id="${e.uni.id}">
            <div class="uni-card-header"><div class="uni-card-name">${esc(uniName)}</div><span class="uni-card-level ${getLevelClass(e.uni.level)}">${e.uni.level.split('/')[0]}</span></div>
            <div class="uni-card-meta"><span>📍${e.uni.loc}</span><span>#${e.uni.rank}</span></div>
            ${e.programs.length > 0 ? `<div class="uni-card-stats">${e.programs.slice(0,2).map(p => `<span class="uni-stat">起薪 <strong>${formatSalary(p.salary_entry)}</strong></span>`).join('')}</div>` : ''}
          </div>`;
        }
        return `<div class="uni-card"><div class="uni-card-name">${esc(uniName)}</div></div>`;
      }).join('')}</div>`;
  } catch(e) { toast('加载失败'); }
}

// ── 论坛 ──
let forumSearchTimer = null;
let selectedForumTag = '';
let bookmarkedPosts = new Set();

async function loadForum(page = 1) {
  currentForumPage = page;
  const sort = $('forumSort')?.value || 'recent';
  const cat = selectedForumCategory || '';
  const keyword = $('forumSearch')?.value?.trim() || '';
  const params = new URLSearchParams({sort, limit:15, offset:(page-1)*15});
  if (cat) params.set('category', cat);
  if (keyword) params.set('keyword', keyword);
  if (selectedForumTag) params.set('keyword', selectedForumTag); // tag as keyword
  try {
    const r = await apiGet('/forum/posts?' + params);
    $('forumPosts').innerHTML = r.data.map(p => renderPostCard(p)).join('');
    renderPagination('forumPagination', r.total, 15, page, p => loadForum(p));
  } catch(e) {}
  // Load tags
  loadForumTags();
  // Load bookmarks
  loadBookmarks();
}

let selectedForumCategory = '';

async function loadForumTags() {
  try {
    const tags = await apiGet('/forum/tags');
    $('tagCloud').innerHTML = tags.slice(0, 20).map(t =>
      `<span class="tag-item${selectedForumTag===t.name?' active':''}" onclick="selectForumTag('${esc(t.name)}')">${esc(t.name)} <small>${t.count}</small></span>`
    ).join('');
    // Also populate tag select cloud in new post form
    const tagSelect = $('tagSelectCloud');
    if (tagSelect) {
      tagSelect.innerHTML = tags.slice(0, 15).map(t =>
        `<span class="tag-select-item" onclick="toggleTagSelect(this,'${esc(t.name)}')">${esc(t.name)}</span>`
      ).join('');
    }
  } catch(e) {}
}

function selectForumTag(tag) {
  if (selectedForumTag === tag) {
    selectedForumTag = '';
  } else {
    selectedForumTag = tag;
  }
  loadForum(1);
}

let selectedPostTags = [];
function toggleTagSelect(el, tag) {
  const idx = selectedPostTags.indexOf(tag);
  if (idx >= 0) {
    selectedPostTags.splice(idx, 1);
    el.classList.remove('active');
  } else {
    selectedPostTags.push(tag);
    el.classList.add('active');
  }
  $('postTags').value = selectedPostTags.join(',');
}

async function loadBookmarks() {
  try {
    const r = await apiGet(`/forum/bookmarks?session_id=${sessionId}`);
    bookmarkedPosts = new Set(r.data.map(p => p.id));
  } catch(e) {}
}

function isBookmarked(postId) {
  return bookmarkedPosts.has(postId);
}

async function toggleBookmark(postId) {
  try {
    const r = await apiPost(`/forum/posts/${postId}/bookmark`, {session_id: sessionId});
    if (r.status === 'bookmarked') {
      bookmarkedPosts.add(postId);
      toast('已收藏');
    } else {
      bookmarkedPosts.delete(postId);
      toast('已取消收藏');
    }
    // Re-render the bookmark button
    const btn = document.querySelector(`.bookmark-btn[data-id="${postId}"]`);
    if (btn) btn.textContent = bookmarkedPosts.has(postId) ? '⭐已收藏' : '★收藏';
  } catch(e) { toast('操作失败'); }
}

async function reportPost(postId) {
  const reason = prompt('请输入举报原因：');
  if (!reason) return;
  try {
    const r = await apiPost(`/forum/posts/${postId}/report`, {session_id: sessionId, reason});
    if (r.status === 'already_reported') {
      toast('你已经举报过此帖子');
    } else {
      toast('举报成功，感谢你的反馈');
    }
  } catch(e) { toast('举报失败'); }
}

function renderPostCard(p) {
  const timeAgo = formatTimeAgo(p.created_at);
  const isPinned = p.is_pinned;
  const avatarColor = stringToColor(p.author);
  return `<div class="post-card${isPinned?' pinned':''}" data-page="post-detail" data-id="${p.id}">
    ${isPinned ? '<span class="pin-badge">置顶</span>' : ''}
    <div class="post-card-header">
      <div class="post-avatar" style="background:${avatarColor}">${p.author.charAt(0)}</div>
      <div class="post-card-info">
        <div class="post-title">${esc(p.title)}</div>
        <div class="post-meta">
          <span>${esc(p.author)}</span>
          <span>${timeAgo}</span>
          <span>👁 ${p.views}</span>
          <span>👍 ${p.likes}</span>
          <span>💬 ${p.comment_count || 0}</span>
        </div>
      </div>
    </div>
    ${(p.tags && p.tags.length) ? `<div class="post-tags">${p.tags.map(t=>`<span class="post-tag">${esc(t)}</span>`).join('')}</div>` : ''}
    <div class="post-card-category">${esc(p.category)}</div>
  </div>`;
}

function stringToColor(str) {
  const colors = ['#ff4757','#00d68f','#4f8fff','#b18cff','#ff9f43','#ff7eb3','#00d4ff','#ffb800'];
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

function formatTimeAgo(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const date = new Date(dateStr.replace(' ', 'T'));
  const diff = Math.floor((now - date) / 1000);
  if (diff < 60) return '刚刚';
  if (diff < 3600) return Math.floor(diff/60) + '分钟前';
  if (diff < 86400) return Math.floor(diff/3600) + '小时前';
  if (diff < 2592000) return Math.floor(diff/86400) + '天前';
  return dateStr.slice(0,10);
}

async function loadPostDetail(id) {
  try {
    const p = await apiGet('/forum/posts/' + id + '?session_id=' + sessionId);
    const timeAgo = formatTimeAgo(p.created_at);
    const bookmarked = isBookmarked(id);
    $('postDetailContent').innerHTML = `
      <div class="post-detail">
        <button class="btn btn-ghost btn-sm" onclick="navigate('forum')" style="margin-bottom:1rem">←返回论坛</button>
        <div class="post-detail-header">
          <h1>${p.is_pinned ? '<span class="pin-badge">置顶</span>' : ''}${esc(p.title)}</h1>
          <div style="color:var(--text3);font-size:0.85rem;margin:0.5rem 0">
            <span class="post-category-badge">${esc(p.category)}</span>
            <span> · ${esc(p.author)}</span>
            <span> · ${timeAgo}</span>
            <span> · 👁 ${p.views}浏览</span>
            <span> · 👍 ${p.likes}赞</span>
          </div>
          <div class="post-tags" style="margin-bottom:1rem">${(p.tags||[]).map(t=>`<span class="post-tag">${esc(t)}</span>`).join('')}</div>
        </div>
        <div style="line-height:1.8;margin-bottom:2rem;white-space:pre-wrap">${esc(p.content)}</div>
        <div class="post-detail-actions">
          <button class="btn btn-sm btn-ghost" onclick="likePost(${id})">👍 点赞 (${p.likes})</button>
          <button class="btn btn-sm btn-ghost bookmark-btn" data-id="${id}" onclick="toggleBookmark(${id})">${bookmarked?'⭐已收藏':'★收藏'}</button>
          ${p.can_edit ? `<button class="btn btn-sm btn-ghost" onclick="editPost(${id})">✏️ 编辑</button>` : ''}
          ${p.can_edit ? `<button class="btn btn-sm btn-ghost" onclick="deletePost(${id})" style="color:var(--red)">🗑️删除</button>` : ''}
          <button class="btn btn-sm btn-ghost" onclick="reportPost(${id})" style="color:var(--text3)">🚩 举报</button>
        </div>
        <h3 style="margin:1.5rem 0 0.8rem">评论 (${p.comments.length})</h3>
        ${p.comments.map((c, i) => `
          <div class="comment-card">
            <div class="comment-header">
              <span class="comment-floor">${i+1}楼</span>
              <span class="comment-author">${esc(c.author)}</span>
              <span class="comment-time">${formatTimeAgo(c.created_at)}</span>
            </div>
            <div class="comment-text">${esc(c.text)}</div>
            <div class="comment-actions">
              <button class="comment-like-btn" onclick="likeComment(${c.id},this)">👍 ${c.likes}</button>
              <button class="comment-reply-btn" onclick="replyTo('${esc(c.author)}')">回复</button>
            </div>
          </div>`).join('')}
        <form class="comment-form" onsubmit="submitComment(event,${id})">
          <input type="text" id="commentAuthor" class="form-input" placeholder="你的昵称" value="匿名用户">
          <textarea id="commentText" class="form-input form-textarea" placeholder="写下你的评论..." required></textarea>
          <button type="submit" class="btn btn-primary">发表评论</button>
        </form>
      </div>`;
  } catch(e) { toast('加载失败'); }
}

async function likePost(postId) {
  try {
    await apiPost(`/forum/posts/${postId}/like`, {});
    loadPostDetail(postId);
    toast('已点赞');
  } catch(e) { toast('点赞失败'); }
}

async function likeComment(commentId, btn) {
  try {
    await apiPost(`/forum/comments/${commentId}/like`, {});
    const text = btn.textContent;
    const match = text.match(/👍\s*(\d+)/);
    if (match) btn.textContent = `👍 ${parseInt(match[1])+1}`;
  } catch(e) { toast('点赞失败'); }
}

function replyTo(author) {
  const textarea = $('commentText');
  if (textarea) {
    textarea.value = `@${author} `;
    textarea.focus();
  }
}

async function submitComment(e, postId) {
  e.preventDefault();
  const author = $('commentAuthor').value || '匿名用户';
  const text = $('commentText').value;
  if (!text.trim()) return;
  try {
    await apiPost(`/forum/posts/${postId}/comments`, {author, text});
    toast('评论成功');
    loadPostDetail(postId);
  } catch(e) { toast('评论失败'); }
}

// ── 帖子编辑/删除 ──
async function editPost(postId) {
  try {
    const p = await apiGet('/forum/posts/' + postId);
    const newTitle = prompt('修改标题', p.title);
    if (newTitle === null) return;
    const newContent = prompt('修改内容', p.content);
    if (newContent === null) return;
    await fetch(API + '/forum/posts/' + postId + '/edit', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({title: newTitle, content: newContent, session_id: sessionId})
    }).then(r => r.json());
    toast('编辑成功');
    loadPostDetail(postId);
  } catch(e) { toast('编辑失败'); }
}

async function deletePost(postId) {
  if (!confirm('确定要删除这篇帖子吗？此操作不可恢复')) return;
  try {
    await fetch(API + '/forum/posts/' + postId, {
      method: 'DELETE',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({session_id: sessionId})
    }).then(r => r.json());
    toast('已删除');
    navigate('forum');
  } catch(e) { toast('删除失败'); }
}

// ── AI选校 ──
async function submitAiReport(e) {
  e.preventDefault();
  const score = parseInt($('aiScore').value);
  if (!score || score < 300 || score > 750) { toast('请输入有效分数300-750)'); return; }
  userScore = score;
  localStorage.setItem('unipulse_score', score);
  // AI选校报告完全免费
  const province = $('aiProvince').value;
  const interests = $('aiInterests').value;
  const subjects = $('aiSubjects').value;
  const preference = $('aiPreference').value;
  $('aiReportResult').classList.remove('hidden');
  $('aiReportResult').innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>AI正在为你生成选校方案...</p></div>';
  try {
    const params = new URLSearchParams({score, province, interests, subjects, preference});
    const r = await apiGet('/ai-report?' + params);
    renderAiReport(r);
  } catch(e) { toast('生成失败'); }
}

function renderAiReport(r) {
  const groups = [
    {key:'冲', label:'🎯 冲一冲', desc:'分数略高于你的院校，有录取希望', cls:'gap-chong', color:'var(--red)'},
    {key:'稳', label:'✓稳一稳', desc:'分数与你相当，录取概率较大', cls:'gap-wen', color:'var(--green)'},
    {key:'保', label:'🛡️保一保', desc:'分数低于你的院校，确保不滑档', cls:'gap-bao', color:'var(--accent2)'},
  ];
  $('aiReportResult').innerHTML = `
    <div style="text-align:center;margin-bottom:1.5rem;padding:1.5rem;background:var(--surface);border-radius:var(--radius);border:1px solid var(--border)">
      <div style="font-size:2.5rem;font-weight:900;color:var(--accent2)">${r.score}分</div>
      <div style="color:var(--text3)">${r.province} · ${r.preference==='综合'?'综合平衡':r.preference==='就业'?'优先就业':r.preference==='深选'?'优先深选':'优先城市'}</div>
    </div>
    ${groups.map(g => {
      const list = r.suggestions[g.key] || [];
      return `<div class="report-section">
        <h3 style="color:${g.color}">${g.label} <span style="font-size:0.78rem;font-weight:400;color:var(--text3)">${g.desc}</span></h3>
        <div class="report-group">${list.map(u => {
          const gap = u.gaokao_score - r.score;
          return `<div class="report-card" data-page="uni-detail" data-id="${u.id}">
            <div class="rc-name">${esc(u.name)}</div>
            <div class="rc-score">${u.gaokao_score}分· ${u.loc} · ${u.level.split('/')[0]}</div>
            <span class="rc-gap ${g.cls}">${gap>0?'高'+gap+'分':'低'+Math.abs(gap)+'分'}</span>
          </div>`;
        }).join('')}</div>
      </div>`;
    }).join('')}
    <div class="report-section">
      <h3>💡 填报建议</h3>
      <ul class="report-tips">${(r.tips||[]).map(t=>`<li>${t}</li>`).join('')}</ul>
    </div>`;
}

// ── 收藏 ──
async function toggleFav(uniId, btn) {
  try {
    if (btn.classList.contains('active')) {
      await fetch(`${API}/favorites?session_id=${sessionId}&uni_id=${uniId}`, {method:'DELETE'});
      btn.classList.remove('active');
      toast('已取消收藏');
    } else {
      await apiPost(`/favorites?session_id=${sessionId}&uni_id=${uniId}`, {});
      btn.classList.add('active');
      toast('已收藏');
    }
  } catch(e) {}
}

async function loadFavorites() {
  try {
    const list = await apiGet('/favorites/' + sessionId);
    if (list.length === 0) {
      $('favGrid').innerHTML = `<div class="empty-state"><div class="empty-icon">⭐</div><h3>暂无收藏</h3><p>浏览高校时点击⭐收藏</p><button class="btn btn-primary" data-page="universities">去浏览</button></div>`;
    } else {
      $('favGrid').innerHTML = list.map(u => renderUniCard(u)).join('');
    }
  } catch(e) {}
}

// ── 搜索 ──
async function performSearch(q) {
  if (!q) return;
  $('searchQueryDisplay').textContent = `搜索，{q}`;
  try {
    const r = await apiGet('/search?q=' + encodeURIComponent(q));
    let html = '';
    if (r.universities.length) {
      html += `<div class="search-section"><h3>🏫 高校 (${r.universities.length})</h3><div class="uni-grid">${r.universities.map(u=>renderUniCard(u)).join('')}</div></div>`;
    }
    if (r.programs.length) {
      html += `<div class="search-section"><h3>📚 专业</h3>${r.programs.map(p=>`<div class="program-card" data-page="program-detail" data-name="${encodeURIComponent(p.name)}" style="display:inline-block;margin:4px"><span style="font-size:1.2rem">${p.icon}</span> ${p.name}</div>`).join('')}</div>`;
    }
    if (r.posts.length) {
      html += `<div class="search-section"><h3>💬 帖子</h3>${r.posts.map(p=>`<div class="post-card" data-page="post-detail" data-id="${p.id}"><div class="post-title">${esc(p.title)}</div><div class="post-meta">${p.author} · ${p.views}浏览</div></div>`).join('')}</div>`;
    }
    if (!html) html = '<div class="empty-state"><h3>未找到结果/h3></div>';
    $('searchResults').innerHTML = html;
  } catch(e) {}
}

// ── 分页 ──
function renderPagination(containerId, total, limit, current, onClick) {
  const pages = Math.ceil(total / limit);
  if (pages <= 1) { $(containerId).innerHTML = ''; return; }
  let html = '';
  if (current > 1) html += `<button onclick="(${onClick})(${current-1})">上一页</button>`;
  const start = Math.max(1, current - 2);
  const end = Math.min(pages, current + 2);
  for (let i = start; i <= end; i++) {
    html += `<button class="${i===current?'active':''}" onclick="(${onClick})(${i})">${i}</button>`;
  }
  if (current < pages) html += `<button onclick="(${onClick})(${current+1})">下一页</button>`;
  $(containerId).innerHTML = html;
}

// ── 事件绑定 ──
document.addEventListener('DOMContentLoaded', () => {
  // 移动端菜单
  $('mobileToggle')?.addEventListener('click', () => $('mobileMenu').classList.toggle('open'));

  // 搜索
  $('searchBtn')?.addEventListener('click', () => { const q = $('searchInput').value; if (q) navigate('search', {q}); });
  $('searchInput')?.addEventListener('keydown', e => { if (e.key==='Enter') { const q = $('searchInput').value; if (q) navigate('search', {q}); }});

  // 首页分数快捷按钮
  document.querySelectorAll('.quick-score').forEach(btn => {
    btn.addEventListener('click', () => {
      const s = parseInt(btn.dataset.score);
      $('heroScore').value = s;
      doHeroScore(s);
    });
  });
  $('heroScoreBtn')?.addEventListener('click', () => {
    const s = parseInt($('heroScore').value);
    if (s) doHeroScore(s);
  });
  $('heroScore')?.addEventListener('keydown', e => {
    if (e.key==='Enter') { const s = parseInt($('heroScore').value); if (s) doHeroScore(s); }
  });

  function doHeroScore(s) {
    userScore = s;
    localStorage.setItem('unipulse_score', s);
    navigate('ai-report');
    setTimeout(() => { $('aiScore').value = s; $('aiReportForm').dispatchEvent(new Event('submit')); }, 200);
  }

  // 高校列表筛选
  $('uniSearch')?.addEventListener('input', debounce(() => loadUniversities(1), 400));
  $('filterRegion')?.addEventListener('change', () => loadUniversities(1));
  $('filterLevel')?.addEventListener('change', () => loadUniversities(1));
  $('filterType')?.addEventListener('change', () => loadUniversities(1));
  $('sortUni')?.addEventListener('change', () => loadUniversities(1));
  $('filterChance')?.addEventListener('change', () => loadUniversities(1));
  $('clearFilters')?.addEventListener('click', () => {
    $('uniSearch').value = ''; $('filterRegion').value = ''; $('filterLevel').value = ''; $('filterType').value = ''; $('filterChance').value = '';
    loadUniversities(1);
  });

  // 分数滑块
  $('scoreSlider')?.addEventListener('input', e => {
    $('scoreDisplay').textContent = e.target.value + '分';
  });
  $('scoreFilterBtn')?.addEventListener('click', () => {
    filterByScore(parseInt($('scoreSlider').value));
  });

  // 论坛
  $('forumSort')?.addEventListener('change', () => loadForum(1));
  // 论坛搜索框（300ms防抖，
  $('forumSearch')?.addEventListener('input', () => {
    clearTimeout(forumSearchTimer);
    forumSearchTimer = setTimeout(() => loadForum(1), 300);
  });
  // 论坛分类Tab
  document.querySelectorAll('.forum-cat-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.forum-cat-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedForumCategory = btn.dataset.category;
      loadForum(1);
    });
  });
  $('newPostBtn')?.addEventListener('click', () => navigate('new-post'));
  // 编辑器Tab切换
  $('tabWrite')?.addEventListener('click', () => {
    $('tabWrite').classList.add('active');
    $('tabPreview').classList.remove('active');
    $('editorWrite').classList.remove('hidden');
    $('editorPreview').classList.add('hidden');
  });
  $('tabPreview')?.addEventListener('click', () => {
    $('tabPreview').classList.add('active');
    $('tabWrite').classList.remove('active');
    $('editorPreview').classList.remove('hidden');
    $('editorWrite').classList.add('hidden');
    const content = $('postContent')?.value || '';
    $('editorPreview').innerHTML = content ? `<div class="preview-content">${esc(content).replace(/\n/g, '<br>')}</div>` : '<p style="color:var(--text3)">暂无内容</p>';
  });
  // 字数统计
  $('postTitle')?.addEventListener('input', () => {
    $('titleCharCount').textContent = $('postTitle').value.length;
  });
  $('postContent')?.addEventListener('input', () => {
    $('contentCharCount').textContent = $('postContent').value.length;
  });
  $('newPostForm')?.addEventListener('submit', async e => {
    e.preventDefault();
    const data = {
      title: $('postTitle').value,
      category: $('postCategory').value,
      content: $('postContent').value,
      author: $('postAuthor').value || '匿名用户',
      tags: $('postTags').value ? $('postTags').value.split(',').map(t=>t.trim()).filter(Boolean) : []
    };
    try {
      await apiPost('/forum/posts', data);
      toast('发布成功');
      selectedPostTags = [];
      navigate('forum');
    } catch(e) { toast('发布失败'); }
  });

  // AI报告
  $('aiReportForm')?.addEventListener('submit', submitAiReport);

  // 对比
  $('compareGoBtn')?.addEventListener('click', doCompare);
  initCompareSearch();

  // 加载首页
  navigate('home');
});

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

// ── 对比搜索器 ──
function initCompareSearch() {
  const input = $('compareSearchInput');
  const dropdown = $('compareSearchDropdown');
  if (!input || !dropdown) return;
  let timer = null;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (!q) { dropdown.classList.add('hidden'); return; }
    timer = setTimeout(async () => {
      try {
        const r = await apiGet('/universities?q=' + encodeURIComponent(q) + '&limit=8');
        if (r.data.length === 0) {
          dropdown.innerHTML = '<div class="compare-search-item" style="color:var(--text3)">未找到匹配院校</div>';
        } else {
          dropdown.innerHTML = r.data.map(u => `
            <div class="compare-search-item" onclick="addCompareFromSearch(${u.id},'${esc(u.name)}',${u.gaokao_score})">
              <span class="cs-name">${esc(u.name)}</span>
              <span class="cs-meta">${u.loc} · ${u.level.split('/')[0]} · ${u.gaokao_score}分</span>
            </div>`).join('');
        }
        dropdown.classList.remove('hidden');
      } catch(e) { dropdown.classList.add('hidden'); }
    }, 300);
  });
  document.addEventListener('click', e => {
    if (!input.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.classList.add('hidden');
    }
  });
}

function addCompareFromSearch(id, name, score) {
  if (compareList.length >= 5) { toast('最多对比5所'); return; }
  if (compareList.some(c => c.id === id)) { toast('已在对比中'); return; }
  compareList.push({id, name, score});
  localStorage.setItem('unipulse_compare', JSON.stringify(compareList));
  renderCompareSlots();
  $('compareSearchInput').value = '';
  $('compareSearchDropdown').classList.add('hidden');
  toast('已加入对比');
}

// ── 骨架屏控制 ──
function showUniGridSkeleton() {
  const sk = $('uniGridSkeleton');
  const grid = $('uniGrid');
  if (sk) sk.style.display = 'grid';
  if (grid) grid.innerHTML = '';
}
function hideUniGridSkeleton() {
  const sk = $('uniGridSkeleton');
  if (sk) sk.style.display = 'none';
}

// ── 冲稳保过滤 ──
function setChanceFilter(filter) {
  chanceFilter = filter;
  loadUniversities(1);
}

// ══════════════════════════════════════
// ── 志愿表功能──
// ══════════════════════════════════════

function addToWish(uniId, name, score) {
  if (wishList.length >= 30) { toast('志愿表最多30个'); return; }
  if (wishList.some(w => w.id === uniId)) { toast('已在志愿表中'); return; }
  // 自动判断冲稳保分综
  const gap = userScore ? userScore - score : 0;
  let group = '稳';
  if (gap < 0) group = '冲';
  else if (gap >= 20) group = '保';
  wishList.push({ id: uniId, name, score, group });
  localStorage.setItem('unipulse_wish', JSON.stringify(wishList));
  // 同步到服务端
  apiPost('/wish-table/add', { session_id: sessionId, uni_id: uniId, group }).catch(() => {});
  toast(`已添加到志愿表[${group}]`);
  // 刷新当前页的卡片状态
  if (currentPage === 'universities') loadUniversities(currentUniPage);
  else if (currentPage === 'wish-table') loadWishTable();
  updateWishBadge();
}

function removeFromWish(uniId) {
  wishList = wishList.filter(w => w.id !== uniId);
  localStorage.setItem('unipulse_wish', JSON.stringify(wishList));
  apiGet(`/wish-table/remove?session_id=${sessionId}&uni_id=${uniId}`).catch(() => {});
  loadWishTable();
  updateWishBadge();
}

function moveWishGroup(uniId, newGroup) {
  const item = wishList.find(w => w.id === uniId);
  if (item) {
    item.group = newGroup;
    localStorage.setItem('unipulse_wish', JSON.stringify(wishList));
    loadWishTable();
  }
}

function clearWishTable() {
  if (!confirm('确定清空志愿表？')) return;
  wishList = [];
  localStorage.setItem('unipulse_wish', JSON.stringify(wishList));
  apiGet(`/wish-table/clear?session_id=${sessionId}`).catch(() => {});
  loadWishTable();
  updateWishBadge();
}

function updateWishBadge() {
  const nav = $('navWish');
  if (nav) {
    const cnt = wishList.length;
    nav.textContent = cnt > 0 ? `📋 志愿表(${cnt})` : '📋 志愿表';
  }
}

async function loadWishTable() {
  // 尝试从服务端同步
  try {
    const serverData = await apiGet('/wish-table/' + sessionId);
    // Merge: server data as source of truth if available
    if (serverData.冲.length || serverData.稳.length || serverData.保.length) {
      wishList = [];
      ['冲','稳','保'].forEach(g => {
        (serverData[g]||[]).forEach(u => {
          if (!wishList.some(w => w.id === u.id)) {
            wishList.push({ id: u.id, name: u.cn, score: u.gaokao_score, group: g });
          }
        });
      });
      localStorage.setItem('unipulse_wish', JSON.stringify(wishList));
    }
  } catch(e) {}

  const groups = { '冲': [], '稳': [], '保': [] };
  wishList.forEach(w => { if (groups[w.group]) groups[w.group].push(w); });

  const total = wishList.length;
  $('wishChongCount').textContent = groups['冲'].length;
  $('wishWenCount').textContent = groups['稳'].length;
  $('wishBaoCount').textContent = groups['保'].length;
  $('wishTotalCount').textContent = total;

  const isEmpty = total === 0;
  $('wishEmpty')?.classList.toggle('hidden', !isEmpty);
  $('wishGroupView')?.classList.toggle('hidden', isEmpty);
  $('wishTips')?.classList.toggle('hidden', isEmpty);

  // Render groups
  ['冲','稳','保'].forEach(g => {
    const container = $('wishItems' + (g==='冲'?'Chong':g==='稳'?'Wen':'Bao'));
    if (!container) return;
    container.innerHTML = groups[g].map((w, i) => `
      <div class="wish-item" draggable="true" data-wish-id="${w.id}" data-wish-group="${g}" data-wish-idx="${i}">
        <span class="wish-drag-handle" title="拖拽排序">★</span>
        <span class="wish-item-order">${i+1}</span>
        <div class="wish-item-info">
          <div class="wish-item-name">${esc(w.name)}</div>
          <div class="wish-item-meta">${w.score}分· ${g}综</div>
        </div>
        <div class="wish-item-btns">
          ${g!=='冲'?'<button class="btn btn-xs btn-ghost" onclick="moveWishGroup('+w.id+',\'冲\')" title="移到冲组">🎯</button>':''}
          ${g!=='稳'?'<button class="btn btn-xs btn-ghost" onclick="moveWishGroup('+w.id+',\'稳\')" title="移到稳组">✓</button>':''}
          ${g!=='保'?'<button class="btn btn-xs btn-ghost" onclick="moveWishGroup('+w.id+',\'保\')" title="移到保组">🛡️</button>':''}
          <button class="btn btn-xs btn-ghost" onclick="navigate('uni-detail',{id:${w.id}})" title="查看详情">👁️</button>
          <button class="btn btn-xs btn-ghost" style="color:var(--red)" onclick="removeFromWish(${w.id})" title="移除">✕</button>
        </div>
      </div>`).join('') || '<div class="wish-empty-group">点击高校卡片上的 +志愿表添加</div>';
    // Bind drag events after render
    initWishDragDrop(container, g);
  });

  // Render list view
  renderWishListView(groups);
  updateWishBadge();
}

function renderWishListView(groups) {
  const all = [];
  ['冲','稳','保'].forEach(g => {
    groups[g].forEach((w, i) => all.push({...w, order: all.length + 1}));
  });
  const table = $('wishListTable');
  if (!table) return;
  if (all.length === 0) { table.innerHTML = ''; return; }
  table.innerHTML = `<table class="emp-table">
    <thead><tr><th>序号</th><th>分组</th><th>院校</th><th>参考线</th><th>与我的差距</th><th>操作</th></tr></thead>
    <tbody>${all.map((w,i) => {
      const gap = userScore ? userScore - w.score : null;
      return `<tr>
        <td>${i+1}</td>
        <td><span class="uni-card-chance ${w.group==='冲'?'chance-chong':w.group==='稳'?'chance-wen':'chance-bao'}">${w.group}</span></td>
        <td><strong>${esc(w.name)}</strong></td>
        <td>${w.score}分</td>
        <td>${gap!==null?(gap>=0?'+':'')+gap+'分':'-'}</td>
        <td><button class="btn btn-xs btn-ghost" style="color:var(--red)" onclick="removeFromWish(${w.id})">移除</button></td>
      </tr>`;
    }).join('')}</tbody></table>`;
}

function switchWishMode(mode) {
  document.querySelectorAll('.wish-mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
  $('wishGroupView')?.classList.toggle('hidden', mode !== 'group');
  $('wishListView')?.classList.toggle('hidden', mode !== 'list');
}

async function exportWishTable(format) {
  try {
    if (format === 'csv') {
      const url = `/api/wish-table/${sessionId}/export?format=csv`;
      const a = document.createElement('a');
      a.href = url; a.download = 'wish_table.csv'; a.click();
      toast('CSV导出成功');
    } else {
      const data = await apiGet('/wish-table/' + sessionId);
      const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = 'wish_table.json'; a.click();
      toast('JSON导出成功');
    }
  } catch(e) { toast('导出失败'); }
}

// ── AI报告增加"一键加入志愿表" ──
const _origRenderAiReport = renderAiReport;
renderAiReport = function(r) {
  _origRenderAiReport(r);
  // Add "一键加入志愿表" buttons to each report card
  document.querySelectorAll('.report-card').forEach(card => {
    const id = parseInt(card.dataset.id);
    const nameEl = card.querySelector('.rc-name');
    const scoreEl = card.querySelector('.rc-score');
    if (id && nameEl) {
      const name = nameEl.textContent;
      const score = parseInt(scoreEl?.textContent) || 0;
      const btn = document.createElement('button');
      btn.className = 'btn btn-xs btn-ghost';
      btn.textContent = '+志愿表';
      btn.onclick = (e) => { e.stopPropagation(); addToWish(id, name, score); };
      card.appendChild(btn);
    }
  });
};


// ── 志愿表拖拽排序──
let dragSrcWishId = null;
let dragSrcGroup = null;

function initWishDragDrop(container, group) {
  const items = container.querySelectorAll('.wish-item[draggable]');
  items.forEach(item => {
    item.addEventListener('dragstart', e => {
      dragSrcWishId = parseInt(item.dataset.wishId);
      dragSrcGroup = item.dataset.wishGroup;
      item.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', dragSrcWishId);
    });
    item.addEventListener('dragend', () => {
      item.classList.remove('dragging');
      document.querySelectorAll('.wish-drop-indicator').forEach(el => el.remove());
    });
    item.addEventListener('dragover', e => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      // Show drop indicator
      const rect = item.getBoundingClientRect();
      const midY = rect.top + rect.height / 2;
      const existing = item.parentNode.querySelector('.wish-drop-indicator');
      if (existing) existing.remove();
      const indicator = document.createElement('div');
      indicator.className = 'wish-drop-indicator';
      if (e.clientY < midY) {
        item.parentNode.insertBefore(indicator, item);
      } else {
        item.parentNode.insertBefore(indicator, item.nextSibling);
      }
    });
    item.addEventListener('drop', e => {
      e.preventDefault();
      const targetId = parseInt(item.dataset.wishId);
      const targetGroup = item.dataset.wishGroup;
      if (dragSrcWishId && dragSrcWishId !== targetId && dragSrcGroup === targetGroup) {
        reorderWishItem(dragSrcWishId, targetId, targetGroup, e.clientY < item.getBoundingClientRect().top + item.getBoundingClientRect().height / 2 ? 'before' : 'after');
      }
      document.querySelectorAll('.wish-drop-indicator').forEach(el => el.remove());
    });
  });
}

function reorderWishItem(srcId, targetId, group, position) {
  const groupItems = wishList.filter(w => w.group === group);
  const others = wishList.filter(w => w.group !== group);
  const srcIdx = groupItems.findIndex(w => w.id === srcId);
  const targetIdx = groupItems.findIndex(w => w.id === targetId);
  if (srcIdx === -1 || targetIdx === -1) return;
  const [moved] = groupItems.splice(srcIdx, 1);
  const newTargetIdx = groupItems.findIndex(w => w.id === targetId);
  const insertIdx = position === 'before' ? newTargetIdx : newTargetIdx + 1;
  groupItems.splice(insertIdx, 0, moved);
  wishList = [...others, ...groupItems];
  localStorage.setItem('unipulse_wish', JSON.stringify(wishList));
  loadWishTable();
}

// ── 浏览模式切换 ──
function switchBrowseMode(mode) {
  browseMode = mode;
  localStorage.setItem('unipulse_browse_mode', mode);
  document.querySelectorAll('.mode-switch-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
  if (mode === 'major') {
    navigate('major-browse');
  } else {
    navigate('universities');
  }
}

async function loadMajorBrowse() {
  try {
    const p = await apiGet('/majors');
    const majorGrid = $('majorBrowseGrid');
    if (!majorGrid) return;
    majorGrid.innerHTML = p.map(pr => `
      <div class="major-browse-card" data-page="program-detail" data-name="${encodeURIComponent(pr.name)}">
        <div class="major-browse-icon">${pr.icon || '📚'}</div>
        <div class="major-browse-name">${esc(pr.name)}</div>
        <div class="major-browse-count">${pr.count || 0}所高校</div>
      </div>`).join('');
    // Update mode buttons
    document.querySelectorAll('.mode-switch-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === 'major'));
  } catch(e) { toast('加载专业列表失败'); }
}

// ══════════════════════════════════════
// ── 发帖功能 ──
// ══════════════════════════════════════
function initNewPostPage() {
  const titleInput = $('postTitle');
  const titleCount = $('titleCharCount');
  if (titleInput && titleCount) {
    titleInput.oninput = () => { titleCount.textContent = titleInput.value.length; };
  }
  const form = $('newPostForm');
  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      await submitNewPost();
    };
  }
  // 编辑器Tab切换已绑定在全局事件不
  // Tag选择已绑定在全局事件不
}

async function submitNewPost() {
  const title = $('postTitle')?.value?.trim();
  const content = $('postContent')?.value?.trim();
  const category = $('postCategory')?.value || '讨论';
  const tagsEl = document.querySelector('.tag-select.active');
  const tags = tagsEl ? tagsEl.dataset.tag : '';

  if (!title) { toast('请输入标题'); return; }
  if (!content) { toast('请输入内容'); return; }

  try {
    await apiPost('/forum/posts', { title, content, category, tags });
    toast('发布成功');
    $('postTitle').value = '';
    $('postContent').value = '';
    if ($('titleCharCount')) $('titleCharCount').textContent = '0';
    document.querySelectorAll('.tag-select.active').forEach(t => t.classList.remove('active'));
    navigate('forum');
  } catch(e) { toast('发布失败'); }
}

// ══════════════════════════════════════
// ── 对比雷达图──
// ══════════════════════════════════════
function drawCompareRadar(canvasId, unis) {
  const canvas = $(canvasId);
  if (!canvas || unis.length < 2) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width; const H = canvas.height;
  const cx = W / 2; const cy = H / 2;
  const R = Math.min(W, H) / 2 - 40;

  const dims = ['综合实力', '学科建设', '就业质量', '师资力量', '国际化', '科研水平'];
  const n = dims.length;
  const angles = dims.map((_, i) => (Math.PI * 2 * i / n) - Math.PI / 2);

  // Clear
  ctx.clearRect(0, 0, W, H);

  // Draw grid
  ctx.strokeStyle = 'rgba(255,255,255,0.1)';
  ctx.lineWidth = 1;
  for (let level = 1; level <= 5; level++) {
    const r = R * level / 5;
    ctx.beginPath();
    angles.forEach((a, i) => {
      const x = cx + r * Math.cos(a); const y = cy + r * Math.sin(a);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.closePath(); ctx.stroke();
  }
  // Draw axes
  angles.forEach(a => {
    ctx.beginPath(); ctx.moveTo(cx, cy);
    ctx.lineTo(cx + R * Math.cos(a), cy + R * Math.sin(a));
    ctx.stroke();
  });
  // Labels
  ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.font = '12px sans-serif'; ctx.textAlign = 'center';
  dims.forEach((d, i) => {
    ctx.fillText(d, cx + (R + 20) * Math.cos(angles[i]), cy + (R + 20) * Math.sin(angles[i]));
  });

  // Draw data polygons
  const colors = ['rgba(59,130,246,0.3)', 'rgba(239,68,68,0.3)'];
  const borders = ['rgba(59,130,246,1)', 'rgba(239,68,68,1)'];
  unis.forEach((u, ui) => {
    const s = u.score || 0;
    const empRate = u.employment_rate || 0;
    const salary = (u.avg_salary || 0) / 100; // normalize
    const vals = [
      Math.min(100, s / 7), // 综合实力
      Math.min(100, s / 8), // 学科建设
      Math.min(100, empRate * 1.2), // 就业质量
      Math.min(100, s / 7.5), // 师资
      Math.min(100, s / 8 + 5), // 国际化
      Math.min(100, s / 6.5 + 3)  // 科研
    ];
    ctx.fillStyle = colors[ui] || colors[0];
    ctx.strokeStyle = borders[ui] || borders[0];
    ctx.lineWidth = 2;
    ctx.beginPath();
    vals.forEach((v, i) => {
      const r = R * v / 100;
      const x = cx + r * Math.cos(angles[i]); const y = cy + r * Math.sin(angles[i]);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.closePath(); ctx.fill(); ctx.stroke();
  });
}

/* UniPulse — 高考志愿填报神器 · 前端逻辑 */
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
  if (gap >= 20) return {text:'较稳', cls:'chance-wen', group:'稳'};
  if (gap >= 0) return {text:'可冲', cls:'chance-chong', group:'冲'};
  if (gap >= -20) return {text:'保底', cls:'chance-bao', group:'保'};
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
      return `<div class="score-dist-bar" onclick="navigate('universities');$('scoreSlider').value=${parseInt(d.range.split('-')[0])};$('scoreDisplay').textContent='${d.range.split('-')[0]}分';filterByScore(${parseInt(d.range.split('-')[0])})">
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
    $('forumPreview').innerHTML = r.data.map(p => `
      <div class="post-card" data-page="post-detail" data-id="${p.id}">
        <div class="post-title">${esc(p.title)}</div>
        <div class="post-meta">${p.author} · ${p.views}浏览 · ${p.likes}赞</div>
      </div>`).join('');
  } catch(e) {}
}

// ── 高校卡片渲染 ──
function renderUniCard(u, showChance = false) {
  const gap = userScore ? userScore - u.gaokao_score : null;
  const chance = gap !== null ? getChanceInfo(gap) : null;
  const isFav = false;
  return `<div class="uni-card" data-page="uni-detail" data-id="${u.id}">
    <button class="uni-card-fav ${isFav?'active':''}" onclick="event.stopPropagation();toggleFav(${u.id},this)">⭐</button>
    <div class="uni-card-header">
      <div class="uni-card-name">${esc(u.cn)}</div>
      <span class="uni-card-level ${getLevelClass(u.level)}">${u.level.split('/')[0]}</span>
    </div>
    <div class="uni-card-meta">
      <span>📍${u.loc}</span><span>${u.type}</span><span>排名#${u.rank}</span>
    </div>
    <div class="uni-card-score">
      <span class="val">${u.gaokao_score}</span><span class="unit">分参考线</span>
    </div>
    ${chance ? `<div class="uni-card-chance ${chance.cls}">${userScore}分 · ${chance.text}（差${Math.abs(gap)}分）</div>` : ''}
    <div class="uni-card-stats">
      <span class="uni-stat">就业率 <strong>${u.employment_rate}%</strong></span>
      <span class="uni-stat">起薪 <strong>${formatSalary(u.avg_salary)}</strong></span>
      <span class="uni-stat">⭐${u.stars}</span>
    </div>
  </div>`;
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// ── 高校列表 ──
async function loadUniversities(page = 1) {
  currentUniPage = page;
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
    $('uniResultsInfo').textContent = `共 ${r.total} 所高校`;
    $('uniGrid').innerHTML = r.data.map(u => renderUniCard(u, true)).join('');
    renderPagination('uniPagination', r.total, 20, page, p => loadUniversities(p));
  } catch(e) { toast('加载失败'); }
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
      <button class="btn btn-ghost btn-sm" onclick="navigate('universities')" style="margin-bottom:1rem">← 返回高校列表</button>
      <div class="uni-detail-header">
        <div class="uni-detail-info">
          <h1>${esc(u.cn)}</h1>
          <div style="color:var(--text3);font-size:0.9rem;margin-bottom:0.3rem">${esc(u.name)}</div>
          <div class="uni-detail-tags">
            ${(u.tags||[]).map(t => `<span class="tag tag-${tagType(t.text)}">${t.text}</span>`).join('')}
          </div>
          <p style="color:var(--text2);font-size:0.88rem;margin-top:0.8rem">${esc(u.description)}</p>
          ${chance ? `<div style="margin-top:1rem"><span class="uni-card-chance ${chance.cls}" style="font-size:0.9rem;padding:6px 16px">${userScore}分 · ${chance.text}（差${Math.abs(gap)}分）</span></div>` : ''}
        </div>
        <div class="uni-detail-score-box">
          <div class="label">参考分数线</div>
          <div class="big">${u.gaokao_score}</div>
          <div class="label">排名 #${u.rank}</div>
          <div style="margin-top:0.8rem">
            <button class="btn btn-ghost btn-sm" onclick="addToCompare(${u.id},'${esc(u.cn)}',${u.gaokao_score})">⚖️ 加入对比</button>
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
      ${u.programs.map(p => p.description ? `<p style="font-size:0.82rem;color:var(--text3);margin-top:0.5rem"><strong>${esc(p.program_name)}：</strong>${esc(p.description)}</p>` : '').join('')}
      ` : ''}
    </div>`;
  } catch(e) { toast('加载失败'); }
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
        <button class="slot-remove" onclick="removeCompare(${i})">✕</button>
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
  const q = prompt('输入高校名称搜索：');
  if (!q) return;
  try {
    const r = await apiGet('/universities?q=' + encodeURIComponent(q) + '&limit=8');
    if (r.data.length === 0) { toast('未找到'); return; }
    const choice = r.data.length === 1 ? r.data[0] : r.data.find(u => u.cn === q) || r.data[0];
    compareList[slot] = {id: choice.id, name: choice.cn, score: choice.gaokao_score};
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
  const fields = [
    {label:'排名', key:'rank', fmt:v=>'#'+v, lower:true},
    {label:'参考分数线', key:'gaokao_score', fmt:v=>v+'分', lower:false},
    {label:'就业率', key:'employment_rate', fmt:v=>v+'%', lower:false},
    {label:'平均起薪', key:'avg_salary', fmt:v=>formatSalary(v)+'/月', lower:false},
    {label:'评分', key:'stars', fmt:v=>'⭐'+v, lower:false},
    {label:'学费/年', key:'tuition', fmt:v=>'¥'+v?.toLocaleString(), lower:true},
    {label:'地区', key:'loc', fmt:v=>v},
    {label:'类型', key:'type', fmt:v=>v},
    {label:'层次', key:'level', fmt:v=>v},
  ];
  $('compareResult').classList.remove('hidden');
  $('compareResult').innerHTML = `
    <div class="compare-result">
      <table class="compare-table">
        <thead><tr><th></th>${unis.map(u=>`<th>${esc(u.cn)}</th>`).join('')}</tr></thead>
        <tbody>${fields.map(f => {
          const vals = unis.map(u => u[f.key]);
          const best = f.lower ? Math.min(...vals.filter(v=>v!=null)) : Math.max(...vals.filter(v=>v!=null));
          return `<tr><td>${f.label}</td>${unis.map(u => {
            const v = u[f.key];
            const isBest = v === best && vals.filter(x=>x===best).length === 1;
            return `<td class="${isBest?'best':''}">${f.fmt(v)}</td>`;
          }).join('')}</tr>`;
        }).join('')}
        ${unis[0]?.metrics ? Object.keys(unis[0].metrics).map(k => {
          const vals = unis.map(u => u.metrics?.[k] || 0);
          const best = Math.max(...vals);
          return `<tr><td>${k}</td>${unis.map(u => {
            const v = u.metrics?.[k] || 0;
            return `<td class="${v===best&&vals.filter(x=>x===best).length===1?'best':''}">${v}</td>`;
          }).join('')}</tr>`;
        }).join('') : ''}
        <tr><td>操作</td>${unis.map(u=>`<td><button class="btn btn-ghost btn-sm" data-page="uni-detail" data-id="${u.id}">查看详情</button></td>`).join('')}</tr>
        </tbody>
      </table>
    </div>`;
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
      <button class="btn btn-ghost btn-sm" onclick="navigate('programs')" style="margin-bottom:1rem">← 返回专业列表</button>
      <h1>${d.icon} ${esc(d.name)}</h1>
      <p style="color:var(--text2);margin:0.5rem 0 1rem">共 ${unis.length} 所高校开设此专业</p>
      <div class="uni-grid">${unis.slice(0,20).map(cn => {
        const e = emp[cn];
        if (e) {
          return `<div class="uni-card" data-page="uni-detail" data-id="${e.uni.id}">
            <div class="uni-card-header"><div class="uni-card-name">${esc(cn)}</div><span class="uni-card-level ${getLevelClass(e.uni.level)}">${e.uni.level.split('/')[0]}</span></div>
            <div class="uni-card-meta"><span>📍${e.uni.loc}</span><span>#${e.uni.rank}</span></div>
            ${e.programs.length > 0 ? `<div class="uni-card-stats">${e.programs.slice(0,2).map(p => `<span class="uni-stat">起薪 <strong>${formatSalary(p.salary_entry)}</strong></span>`).join('')}</div>` : ''}
          </div>`;
        }
        return `<div class="uni-card"><div class="uni-card-name">${esc(cn)}</div></div>`;
      }).join('')}</div>`;
  } catch(e) { toast('加载失败'); }
}

// ── 论坛 ──
async function loadForum(page = 1) {
  currentForumPage = page;
  const sort = $('forumSort')?.value || 'recent';
  const cat = $('forumCategory')?.value || '';
  const params = new URLSearchParams({sort, limit:15, offset:(page-1)*15});
  if (cat) params.set('category', cat);
  try {
    const r = await apiGet('/forum/posts?' + params);
    $('forumPosts').innerHTML = r.data.map(p => `
      <div class="post-card" data-page="post-detail" data-id="${p.id}">
        <div class="post-title">${esc(p.title)}</div>
        <div class="post-meta">${p.category} · ${p.author} · ${p.views}浏览 · ${p.likes}赞 · ${p.comment_count}评论</div>
        <div class="post-tags">${(p.tags||[]).map(t=>`<span class="post-tag">${esc(t)}</span>`).join('')}</div>
      </div>`).join('');
    renderPagination('forumPagination', r.total, 15, page, p => loadForum(p));
  } catch(e) {}
}

async function loadPostDetail(id) {
  try {
    const p = await apiGet('/forum/posts/' + id);
    $('postDetailContent').innerHTML = `
      <div class="post-detail">
        <button class="btn btn-ghost btn-sm" onclick="navigate('forum')" style="margin-bottom:1rem">← 返回论坛</button>
        <h1>${esc(p.title)}</h1>
        <div style="color:var(--text3);font-size:0.85rem;margin:0.5rem 0">${p.category} · ${p.author} · ${p.views}浏览 · ${p.likes}赞</div>
        <div class="post-tags" style="margin-bottom:1rem">${(p.tags||[]).map(t=>`<span class="post-tag">${esc(t)}</span>`).join('')}</div>
        <div style="line-height:1.8;margin-bottom:2rem">${esc(p.content)}</div>
        <h3 style="margin-bottom:0.8rem">评论 (${p.comments.length})</h3>
        ${p.comments.map(c => `
          <div class="comment-card">
            <div class="comment-author">${esc(c.author)}</div>
            <div class="comment-text">${esc(c.text)}</div>
            <div class="comment-meta">${c.likes}赞</div>
          </div>`).join('')}
        <form class="comment-form" onsubmit="submitComment(event,${id})">
          <input type="text" id="commentAuthor" class="form-input" placeholder="你的昵称" value="匿名用户">
          <textarea id="commentText" class="form-input form-textarea" placeholder="写下你的评论..." required></textarea>
          <button type="submit" class="btn btn-primary">发表评论</button>
        </form>
      </div>`;
  } catch(e) { toast('加载失败'); }
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

// ── AI选校 ──
async function submitAiReport(e) {
  e.preventDefault();
  const score = parseInt($('aiScore').value);
  if (!score || score < 300 || score > 750) { toast('请输入有效分数(300-750)'); return; }
  userScore = score;
  localStorage.setItem('unipulse_score', score);
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
    {key:'稳', label:'✅ 稳一稳', desc:'分数与你相当，录取概率较大', cls:'gap-wen', color:'var(--green)'},
    {key:'保', label:'🛡️ 保一保', desc:'分数低于你的院校，确保不滑档', cls:'gap-bao', color:'var(--accent2)'},
  ];
  $('aiReportResult').innerHTML = `
    <div style="text-align:center;margin-bottom:1.5rem;padding:1.5rem;background:var(--surface);border-radius:var(--radius);border:1px solid var(--border)">
      <div style="font-size:2.5rem;font-weight:900;color:var(--accent2)">${r.score}分</div>
      <div style="color:var(--text3)">${r.province} · ${r.preference==='综合'?'综合平衡':r.preference==='就业'?'优先就业':r.preference==='深造'?'优先深造':'优先城市'}</div>
    </div>
    ${groups.map(g => {
      const list = r.suggestions[g.key] || [];
      return `<div class="report-section">
        <h3 style="color:${g.color}">${g.label} <span style="font-size:0.78rem;font-weight:400;color:var(--text3)">${g.desc}</span></h3>
        <div class="report-group">${list.map(u => {
          const gap = u.gaokao_score - r.score;
          return `<div class="report-card" data-page="uni-detail" data-id="${u.id}">
            <div class="rc-name">${esc(u.cn)}</div>
            <div class="rc-score">${u.gaokao_score}分 · ${u.loc} · ${u.level.split('/')[0]}</div>
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
  $('searchQueryDisplay').textContent = `搜索：${q}`;
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
    if (!html) html = '<div class="empty-state"><h3>未找到结果</h3></div>';
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
  $('clearFilters')?.addEventListener('click', () => {
    $('uniSearch').value = ''; $('filterRegion').value = ''; $('filterLevel').value = ''; $('filterType').value = '';
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
  $('forumCategory')?.addEventListener('change', () => loadForum(1));
  $('newPostBtn')?.addEventListener('click', () => navigate('new-post'));
  $('newPostForm')?.addEventListener('submit', async e => {
    e.preventDefault();
    const data = {
      title: $('postTitle').value,
      category: $('postCategory').value,
      content: $('postContent').value,
      author: $('postAuthor').value || '匿名用户',
      tags: $('postTags').value ? $('postTags').value.split(',').map(t=>t.trim()) : []
    };
    try {
      await apiPost('/forum/posts', data);
      toast('发布成功');
      navigate('forum');
    } catch(e) { toast('发布失败'); }
  });

  // AI报告
  $('aiReportForm')?.addEventListener('submit', submitAiReport);

  // 对比
  $('compareGoBtn')?.addEventListener('click', doCompare);

  // 加载首页
  navigate('home');
});

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

/* UniPulse v4.0 — 高考志愿智能助手 · 前端核心 */
(function() {
  'use strict';
  
  const API = '';
  let allUnis = [];
  let allPrograms = [];
  let currentPage = 'home';
  let userScore = 0;
  let userProvince = '';
  let userType = '理科';
  let wishTable = { chong: [], wen: [], bao: [] };
  let favorites = JSON.parse(localStorage.getItem('up_fav') || '[]');
  let wishSessionId = localStorage.getItem('up_wish_sid') || ('sid_' + Date.now());
  
  // === 初始化 ===
  async function init() {
    loadWishTable();
    bindEvents();
    await Promise.all([loadUnis(), loadPrograms(), loadStats()]);
    navigate('home');
  }
  
  // === API调用 ===
  async function api(path) {
    try {
      const r = await fetch(API + path);
      return await r.json();
    } catch(e) { console.error('API error:', path, e); return null; }
  }
  
  // === 数据加载 ===
  async function loadUnis() {
    const r = await api('/api/universities?limit=3000');
    if (r && r.universities) allUnis = r.universities;
  }
  
  async function loadPrograms() {
    const r = await api('/api/majors');
    if (r && r.majors) allPrograms = r.majors;
  }
  
  async function loadStats() {
    const r = await api('/api/stats');
    if (!r) return;
    const el = document.getElementById('heroStats');
    if (el) {
      el.innerHTML = `
        <div class="hero-stat"><div class="hero-stat-num">${r.univers || 0}+</div><div class="hero-stat-label">所高校</div></div>
        <div class="hero-stat"><div class="hero-stat-num">${r.employment_records || 0}+</div><div class="hero-stat-label">条就业数据</div></div>
        <div class="hero-stat"><div class="hero-stat-num">${r.majors || 0}</div><div class="hero-stat-label">个专业</div></div>
      `;
    }
  }
  
  // === 导航 ===
  function navigate(page, data) {
    currentPage = page;
    document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
    const el = document.getElementById('page-' + page);
    if (el) el.classList.remove('hidden');
    window.scrollTo(0, 0);
    
    switch(page) {
      case 'home': renderHome(); break;
      case 'universities': renderUniList(); break;
      case 'uni-detail': renderUniDetail(data); break;
      case 'programs': renderPrograms(); break;
      case 'program-detail': renderProgramDetail(data); break;
      case 'forum': renderForum(); break;
      case 'compare': renderCompare(); break;
      case 'wish-table': renderWishTable(); break;
      case 'ai-report': renderAIForm(); break;
      case 'favorites': renderFavorites(); break;
      case 'post-detail': renderPostDetail(data); break;
    }
  }
  
  // === 首页 ===
  function renderHome() {
    renderHotUnis();
    renderScoreDist();
    renderProgramGrid('programGrid');
    renderForumPreview();
  }
  
  function renderHotUnis() {
    const el = document.getElementById('hotUnis');
    if (!el) return;
    const hot = allUnis.filter(u => u.f985 || u.f211).slice(0, 8);
    el.innerHTML = hot.map(u => uniCard(u)).join('');
  }
  
  function renderScoreDist() {
    const el = document.getElementById('scoreDistChart');
    if (!el || allUnis.length === 0) return;
    const ranges = ['300-400','400-450','450-500','500-530','530-560','560-580','580-600','600-620','620-650','650-680','680-750'];
    const counts = ranges.map(r => {
      const [lo, hi] = r.split('-').map(Number);
      return allUnis.filter(u => u.gaokao_score >= lo && u.gaokao_score < hi).length;
    });
    const max = Math.max(...counts, 1);
    el.innerHTML = '<div style="display:flex;align-items:flex-end;gap:4px;height:120px;padding:8px 0">' +
      ranges.map((r, i) => `<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px">
        <span style="font-size:11px;color:var(--gray-500)">${counts[i]}</span>
        <div style="width:100%;background:var(--primary);border-radius:4px 4px 0 0;height:${Math.max(counts[i]/max*100, 2)}%;opacity:${0.4+0.6*counts[i]/max};transition:height .3s"></div>
        <span style="font-size:10px;color:var(--gray-400);white-space:nowrap">${r}</span>
      </div>`).join('') + '</div>';
  }
  
  function renderProgramGrid(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = allPrograms.slice(0, 12).map(p => `
      <div class="program-card" data-page="program-detail" data-id="${p.id}">
        <div class="program-card-name">${p.name}</div>
        <div class="program-card-count">${p.university_count || 0}所</div>
      </div>
    `).join('');
  }
  
  async function renderForumPreview() {
    const el = document.getElementById('forumPreview');
    if (!el) return;
    const r = await api('/api/forum?page=1&limit=3');
    if (!r || !r.posts) { el.innerHTML = '<p style="color:var(--gray-400)">暂无讨论</p>'; return; }
    el.innerHTML = r.posts.map(p => `
      <div class="post-card" data-page="post-detail" data-id="${p.id}">
        <div class="post-card-title">${esc(p.title)}</div>
        <div class="post-card-meta">
          <span>${p.author || '匿名'}</span>
          <span>${p.comment_count || 0}评论</span>
          <span>${timeAgo(p.created_at)}</span>
        </div>
      </div>
    `).join('');
  }
  
  // === 高校卡片 ===
  function uniCard(u, chance) {
    const tags = [];
    if (u.f985) tags.push('<span class="tag tag-985">985</span>');
    if (u.f211) tags.push('<span class="tag tag-211">211</span>');
    if (u.dual_class) tags.push('<span class="tag tag-dual">双一流</span>');
    if (chance === '冲') tags.push('<span class="tag tag-chong">冲</span>');
    if (chance === '稳') tags.push('<span class="tag tag-wen">稳</span>');
    if (chance === '保') tags.push('<span class="tag tag-bao">保</span>');
    const score = u.gaokao_score || u.score || 0;
    return `<div class="uni-card" data-page="uni-detail" data-id="${u.id}">
      <div class="uni-card-header">
        <div class="uni-card-name">${esc(u.name)}</div>
        <div class="uni-card-tags">${tags.join('')}</div>
      </div>
      <div class="uni-card-meta">
        <span>${esc(u.province || u.cn || '')}</span>
        <span>${esc(u.type || '')}</span>
      </div>
      ${score > 0 ? `<div class="uni-card-score"><span class="score-num">${score}</span><span class="score-label">参考分数线</span></div>` : ''}
      <div class="uni-card-bottom">
        <span>${u.employment_rate ? (u.employment_rate > 1 ? u.employment_rate + '%' : (u.employment_rate * 100).toFixed(0) + '%') : ''} 就业率</span>
        <span>${u.avg_salary ? (u.avg_salary > 1000 ? (u.avg_salary/1000).toFixed(1)+'k' : u.avg_salary+'元') : ''}</span>
      </div>
    </div>`;
  }
  
  // === 高校列表 ===
  function renderUniList() {
    const el = document.getElementById('uniGrid');
    const info = document.getElementById('uniResultsInfo');
    const countEl = document.getElementById('uniCount');
    if (!el) return;
    
    let filtered = [...allUnis];
    const search = (document.getElementById('uniSearch') || {}).value || '';
    const region = (document.getElementById('filterRegion') || {}).value || '';
    const level = (document.getElementById('filterLevel') || {}).value || '';
    const type = (document.getElementById('filterType') || {}).value || '';
    const sort = (document.getElementById('sortUni') || {}).value || 'rank-asc';
    const chanceFilter = (document.getElementById('filterChance') || {}).value || '';
    
    if (search) filtered = filtered.filter(u => u.name.includes(search) || (u.province || '').includes(search));
    if (region) filtered = filtered.filter(u => getRegion(u.province) === region);
    if (level === '985') filtered = filtered.filter(u => u.f985);
    else if (level === '211') filtered = filtered.filter(u => u.f211);
    else if (level === '双一流') filtered = filtered.filter(u => u.dual_class);
    if (type) filtered = filtered.filter(u => (u.type || '').includes(type));
    
    // 排序
    filtered.sort((a, b) => {
      if (sort === 'rank-asc') return (a.rank || 9999) - (b.rank || 9999);
      if (sort === 'score-desc') return (b.gaokao_score || 0) - (a.gaokao_score || 0);
      if (sort === 'salary-desc') return (b.avg_salary || 0) - (a.avg_salary || 0);
      if (sort === 'employment-desc') return (b.employment_rate || 0) - (a.employment_rate || 0);
      return 0;
    });
    
    // 冲稳保过滤
    if (chanceFilter && userScore > 0) {
      filtered = filtered.filter(u => {
        const c = getChance(userScore, u.gaokao_score || 0);
        return c === chanceFilter;
      });
    }
    
    if (countEl) countEl.textContent = `共 ${filtered.length} 所高校`;
    if (info) info.textContent = `找到 ${filtered.length} 所高校`;
    
    const page = 1;
    const perPage = 24;
    const start = (page - 1) * perPage;
    el.innerHTML = filtered.slice(start, start + perPage).map(u => uniCard(u, userScore > 0 ? getChance(userScore, u.gaokao_score || 0) : undefined)).join('');
  }
  
  function getChance(score, uniScore) {
    if (uniScore <= 0) return '';
    const diff = score - uniScore;
    if (diff < -20) return '冲';
    if (diff >= -20 && diff < 15) return '稳';
    return '保';
  }
  
  function getRegion(province) {
    const map = {'北京':'华北','天津':'华北','河北':'华北','山西':'华北','内蒙古':'华北',
      '上海':'华东','江苏':'华东','浙江':'华东','安徽':'华东','福建':'华东','江西':'华东','山东':'华东',
      '河南':'华中','湖北':'华中','湖南':'华中',
      '广东':'华南','广西':'华南','海南':'华南',
      '重庆':'西南','四川':'西南','贵州':'西南','云南':'西南','西藏':'西南',
      '陕西':'西北','甘肃':'西北','青海':'西北','宁夏':'西北','新疆':'西北',
      '辽宁':'东北','吉林':'东北','黑龙江':'东北'};
    return map[province] || '';
  }
  
  // === 高校详情 ===
  async function renderUniDetail(id) {
    const el = document.getElementById('uniDetailContent');
    if (!el) return;
    el.innerHTML = '<div class="loading-skeleton"></div>';
    
    const u = allUnis.find(x => x.id == id);
    if (!u) { el.innerHTML = '<p>未找到该高校</p>'; return; }
    
    // 加载省分数线
    const scores = await api(`/api/universities/${id}/province-scores`);
    
    const tags = [];
    if (u.f985) tags.push('<span class="tag tag-985">985</span>');
    if (u.f211) tags.push('<span class="tag tag-211">211</span>');
    if (u.dual_class) tags.push('<span class="tag tag-dual">双一流</span>');
    
    let html = `
      <div class="detail-header">
        <div class="container">
          <button class="btn btn-ghost btn-sm" data-page="universities" style="margin-bottom:12px">← 返回高校库</button>
          <div class="detail-name">${esc(u.name)}</div>
          <div class="detail-tags">${tags.join(' ')}</div>
          <div class="detail-info">
            <div class="detail-info-item">📍 ${esc(u.province || '')} ${esc(u.city || '')}</div>
            <div class="detail-info-item">🏷️ ${esc(u.type || '')} · ${esc(u.nature || '公办')}</div>
            ${u.gaokao_score ? `<div class="detail-info-item">📊 参考分数线 <span>${u.gaokao_score}</span></div>` : ''}
            ${u.employment_rate ? `<div class="detail-info-item">💼 就业率 <span>${u.employment_rate > 1 ? u.employment_rate + '%' : (u.employment_rate * 100).toFixed(0) + '%'}</span></div>` : ''}
            ${u.avg_salary ? `<div class="detail-info-item">💰 平均薪资 <span>${u.avg_salary > 1000 ? (u.avg_salary/1000).toFixed(1) + 'k' : u.avg_salary + '元'}</span></div>` : ''}
          </div>
        </div>
      </div>
      
      <div class="detail-tabs">
        <button class="detail-tab active" data-tab="scores">省分数线</button>
        <button class="detail-tab" data-tab="info">院校信息</button>
        <button class="detail-tab" data-tab="employment">就业数据</button>
        <button class="detail-tab" data-tab="programs">开设专业</button>
      </div>
      
      <div id="tabContent">
        ${renderScoresTab(scores, u)}
      </div>
    `;
    
    el.innerHTML = html;
    
    // 绑定tab切换
    el.querySelectorAll('.detail-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        el.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const tName = tab.dataset.tab;
        const content = document.getElementById('tabContent');
        if (tName === 'scores') content.innerHTML = renderScoresTab(scores, u);
        else if (tName === 'info') content.innerHTML = renderInfoTab(u);
        else if (tName === 'employment') content.innerHTML = renderEmploymentTab(u);
        else if (tName === 'programs') content.innerHTML = renderProgramsTab(u);
      });
    });
  }
  
  function renderScoresTab(scores, u) {
    const majorScores = scores && scores.major_scores ? scores.major_scores : null;
    const baseScores = scores && scores.base_scores ? scores.base_scores : null;
    if (!majorScores && !baseScores) {
      return '<p style="color:var(--gray-400)">暂无分数线数据</p>';
    }
    
    // 构建省份列表
    const provs = majorScores ? Object.keys(majorScores) : Object.keys(baseScores || {});
    if (provs.length === 0) return '<p style="color:var(--gray-400)">暂无分数线数据</p>';
    
    let html = '';
    
    // 用户分数对比栏
    if (userScore > 0) {
      html += `<div style="background:var(--primary-bg,rgba(37,99,235,0.08));border:1px solid var(--primary);border-radius:8px;padding:12px 16px;margin-bottom:16px;display:flex;align-items:center;gap:12px">
        <span style="font-weight:700;color:var(--primary)">我的分数：${userScore}</span>
        <span style="color:var(--gray-400)">|</span>
        <span style="color:var(--gray-500)">以下分数标色：🟢冲 🔵稳 🟢保</span>
      </div>`;
    }
    
    // 分省折叠展示
    html += '<div class="prov-scores-list">';
    provs.sort().forEach(prov => {
      const majors = majorScores && majorScores[prov] ? majorScores[prov] : [];
      const base = baseScores && baseScores[prov] ? baseScores[prov] : null;
      const majorCount = Array.isArray(majors) ? majors.length : 0;
      const hasMajors = majorCount > 0;
      
      // 冲稳保标记
      let chanceTag = '';
      if (userScore > 0 && base) {
        const diff = userScore - base;
        if (diff < -20) chanceTag = '<span class="tag tag-chong" style="font-size:11px">冲</span>';
        else if (diff < 15) chanceTag = '<span class="tag tag-wen" style="font-size:11px">稳</span>';
        else chanceTag = '<span class="tag tag-bao" style="font-size:11px">保</span>';
      }
      
      html += `<div class="prov-score-item" style="border:1px solid var(--gray-200);border-radius:8px;margin-bottom:8px;overflow:hidden">
        <div class="prov-score-header" style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;cursor:pointer;background:var(--gray-50)" onclick="this.parentElement.querySelector('.prov-score-detail').classList.toggle('hidden')">
          <div style="display:flex;align-items:center;gap:8px">
            <span style="font-weight:600">${esc(prov)}</span>
            ${chanceTag}
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            ${base ? `<span style="font-weight:700;color:var(--primary);font-size:18px">${base}</span><span style="color:var(--gray-400);font-size:12px">分</span>` : ''}
            ${hasMajors ? `<span style="color:var(--gray-400);font-size:12px">${majorCount}个专业组 ▸</span>` : ''}
          </div>
        </div>
        <div class="prov-score-detail hidden" style="padding:0 14px 10px">`;
      
      if (hasMajors) {
        html += '<table class="score-table" style="width:100%;font-size:13px"><thead><tr><th>专业组</th><th>科类</th><th>批次</th><th>最低分</th><th>位次</th><th>选科</th><th>年份</th></tr></thead><tbody>';
        majors.forEach(s => {
          const sDiff = userScore > 0 && s.score ? userScore - s.score : null;
          let rowColor = '';
          if (sDiff !== null) {
            if (sDiff < -20) rowColor = 'background:rgba(239,68,68,0.05)';
            else if (sDiff < 15) rowColor = 'background:rgba(37,99,235,0.05)';
            else rowColor = 'background:rgba(34,197,94,0.05)';
          }
          html += `<tr style="${rowColor}">
            <td>${esc(s.major || s.sp_name || s.subject_group || '-')}</td>
            <td>${esc(s.type || '')}</td>
            <td>${esc(s.batch || '')}</td>
            <td><strong>${s.score || s.min_score || '-'}</strong></td>
            <td>${s.min_rank || '-'}</td>
            <td style="font-size:12px;color:var(--gray-500)">${esc(s.subject_req || '')}</td>
            <td>${s.year || '-'}</td>
          </tr>`;
        });
        html += '</tbody></table>';
      } else if (base) {
        html += `<p style="color:var(--gray-400);padding:8px 0">参考分数线：${base}分</p>`;
      }
      
      html += '</div></div>';
    });
    html += '</div>';
    html += `<p style="color:var(--gray-400);margin-top:12px;font-size:13px">共 ${provs.length} 个省份数据${majorScores ? '（含专业组/选科要求/位次）' : ''}</p>`;
    return html;
  }
  
  function renderInfoTab(u) {
    return `<div class="detail-info" style="grid-template-columns:repeat(auto-fill,minmax(250px,1fr))">
      ${u.founded ? `<div class="detail-info-item">建校年份 <span>${u.founded}</span></div>` : ''}
      ${u.belong ? `<div class="detail-info-item">主管部门 <span>${esc(u.belong)}</span></div>` : ''}
      ${u.motto ? `<div class="detail-info-item">校训 <span>${esc(u.motto)}</span></div>` : ''}
      ${u.num_academician ? `<div class="detail-info-item">院士 <span>${u.num_academician}人</span></div>` : ''}
      ${u.num_doctor ? `<div class="detail-info-item">博士点 <span>${u.num_doctor}个</span></div>` : ''}
      ${u.num_master ? `<div class="detail-info-item">硕士点 <span>${u.num_master}个</span></div>` : ''}
      ${u.num_lab ? `<div class="detail-info-item">重点实验室 <span>${u.num_lab}个</span></div>` : ''}
      ${u.ruanke_rank ? `<div class="detail-info-item">软科排名 <span>第${u.ruanke_rank}名</span></div>` : ''}
      ${u.qs_rank ? `<div class="detail-info-item">QS排名 <span>第${u.qs_rank}名</span></div>` : ''}
    </div>`;
  }
  
  function renderEmploymentTab(u) {
    return `<div class="detail-info">
      ${u.employment_rate ? `<div class="detail-info-item">就业率 <span>${u.employment_rate > 1 ? u.employment_rate + '%' : (u.employment_rate * 100).toFixed(0) + '%'}</span></div>` : ''}
      ${u.avg_salary ? `<div class="detail-info-item">平均薪资 <span>${u.avg_salary > 1000 ? (u.avg_salary/1000).toFixed(1) + 'k/月' : u.avg_salary + '元/月'}</span></div>` : ''}
    </div>
    <p style="color:var(--gray-400);margin-top:16px">更多就业数据持续更新中</p>`;
  }
  
  function renderProgramsTab(u) {
    if (!u.programs || u.programs.length === 0) return '<p style="color:var(--gray-400)">暂无专业数据</p>';
    return '<div class="program-grid">' + u.programs.map(p => `<div class="program-card"><div class="program-card-name">${esc(p.name || p)}</div></div>`).join('') + '</div>';
  }
  
  // === 专业 ===
  function renderPrograms() {
    const el = document.getElementById('programGridFull');
    if (!el) return;
    el.innerHTML = allPrograms.map(p => `
      <div class="program-card" data-page="program-detail" data-id="${p.id}">
        <div class="program-card-name">${esc(p.name)}</div>
        <div class="program-card-count">${p.university_count || 0}所高校</div>
      </div>
    `).join('');
  }
  
  function renderProgramDetail(id) {
    const el = document.getElementById('programDetailContent');
    if (!el) return;
    const p = allPrograms.find(x => x.id == id);
    if (!p) { el.innerHTML = '<p>未找到该专业</p>'; return; }
    const related = allUnis.filter(u => u.programs && u.programs.some(pr => (pr.name || pr) === p.name)).slice(0, 20);
    el.innerHTML = `
      <button class="btn btn-ghost btn-sm" data-page="programs" style="margin-bottom:12px">← 返回专业列表</button>
      <h2 style="font-size:24px;margin-bottom:8px">${esc(p.name)}</h2>
      <p style="color:var(--gray-500);margin-bottom:20px">开设该专业的高校</p>
      <div class="uni-grid">${related.map(u => uniCard(u)).join('')}</div>
    `;
  }
  
  // === 论坛 ===
  async function renderForum() {
    const el = document.getElementById('forumList');
    if (!el) return;
    const r = await api('/api/forum?page=1&limit=20');
    if (!r || !r.posts) { el.innerHTML = '<p style="color:var(--gray-400)">暂无帖子</p>'; return; }
    el.innerHTML = r.posts.map(p => `
      <div class="post-card" data-page="post-detail" data-id="${p.id}">
        <div class="post-card-title">${esc(p.title)}</div>
        <div class="post-card-meta">
          <span>${esc(p.author || '匿名')}</span>
          <span>${p.comment_count || 0}评论</span>
          <span>${timeAgo(p.created_at)}</span>
        </div>
      </div>
    `).join('');
  }
  
  async function renderPostDetail(id) {
    const el = document.getElementById('postDetailContent');
    if (!el) return;
    const r = await api('/api/forum/' + id);
    if (!r) { el.innerHTML = '<p>加载失败</p>'; return; }
    const p = r.post || r;
    el.innerHTML = `
      <button class="btn btn-ghost btn-sm" data-page="forum" style="margin-bottom:12px">← 返回讨论区</button>
      <h2 style="font-size:22px;margin-bottom:8px">${esc(p.title)}</h2>
      <div style="font-size:13px;color:var(--gray-400);margin-bottom:16px">${esc(p.author || '匿名')} · ${timeAgo(p.created_at)}</div>
      <div style="line-height:1.8;margin-bottom:24px">${esc(p.content)}</div>
      <h3 style="margin-bottom:12px">评论 (${(p.comments || []).length})</h3>
      ${(p.comments || []).map(c => `
        <div style="padding:10px 0;border-bottom:1px solid var(--gray-100)">
          <div style="font-size:13px;color:var(--gray-400)">${esc(c.author || '匿名')} · ${timeAgo(c.created_at)}</div>
          <div style="margin-top:4px">${esc(c.content)}</div>
        </div>
      `).join('')}
    `;
  }
  
  // === 对比 ===
  function renderCompare() {
    const el = document.getElementById('compareContent');
    if (!el) return;
    el.innerHTML = `
      <div style="margin-bottom:16px">
        <input type="text" id="compareSearch" class="filter-input" placeholder="搜索高校添加到对比..." style="width:300px">
        <div id="compareSelected" style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap"></div>
      </div>
      <div id="compareResult"></div>
    `;
  }
  
  // === 志愿表 ===
  async function loadWishTable() {
    const r = await api(`/api/wish-table/${wishSessionId}`);
    if (r && r.wish_table) {
      wishTable = r.wish_table;
    }
    updateWishBadge();
  }
  
  function updateWishBadge() {
    const badge = document.getElementById('wishBadge');
    const total = wishTable.chong.length + wishTable.wen.length + wishTable.bao.length;
    if (badge) { badge.textContent = total; badge.style.display = total > 0 ? '' : 'none'; }
  }
  
  function renderWishTable() {
    const el = document.getElementById('wishTableContent');
    if (!el) return;
    
    function renderGroup(title, items, cls) {
      return `<div class="wish-section">
        <div class="wish-section-title ${cls}">${title} (${items.length})</div>
        ${items.length === 0 ? '<p style="color:var(--gray-400);padding:8px 0">暂无</p>' : 
          items.map(u => `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:#fff;border:1px solid var(--gray-200);border-radius:var(--radius);margin-bottom:6px">
            <span style="font-weight:600">${esc(u.name)}</span>
            <div><span style="color:var(--gray-400);font-size:13px">${u.score || ''}</span>
            <button class="btn btn-sm btn-ghost" onclick="window._removeWish('${cls}','${u.id}')">移除</button></div>
          </div>`).join('')}
      </div>`;
    }
    
    el.innerHTML = `
      <div class="page-header"><h1>我的志愿表</h1></div>
      ${renderGroup('🎯 冲一冲', wishTable.chong, 'chong')}
      ${renderGroup('✅ 稳一稳', wishTable.wen, 'wen')}
      ${renderGroup('🛡️ 保一保', wishTable.bao, 'bao')}
      <div style="margin-top:16px;display:flex;gap:8px">
        <button class="btn btn-primary" onclick="window._exportWish('csv')">导出CSV</button>
        <button class="btn btn-ghost" onclick="window._exportWish('json')">导出JSON</button>
        <button class="btn btn-ghost" onclick="window._clearWish()">清空志愿表</button>
      </div>
    `;
  }
  
  window._removeWish = async function(group, id) {
    await api(`/api/wish-table/remove?session_id=${wishSessionId}&group=${group}&university_id=${id}`);
    await loadWishTable();
    renderWishTable();
  };
  
  window._clearWish = async function() {
    await api(`/api/wish-table/clear?session_id=${wishSessionId}`);
    wishTable = { chong: [], wen: [], bao: [] };
    updateWishBadge();
    renderWishTable();
  };
  
  window._exportWish = async function(fmt) {
    window.open(`${API}/api/wish-table/${wishSessionId}/export?format=${fmt}`);
  };
  
  // === AI选校 ===
  function renderAIForm() {
    // 填充省份下拉
    const provSelect = document.getElementById('aiProvince');
    if (provSelect && provSelect.options.length <= 1) {
      const provs = [...new Set(allUnis.map(u => u.province).filter(Boolean))].sort();
      provSelect.innerHTML = provs.map(p => `<option value="${p}">${p}</option>`).join('');
    }
  }
  
  async function generateAIReport() {
    const score = parseInt(document.getElementById('aiScore').value);
    const province = document.getElementById('aiProvince').value;
    const type = document.getElementById('aiType').value;
    const major = document.getElementById('aiMajor').value;
    
    if (!score || score < 300 || score > 750) { alert('请输入有效分数(300-750)'); return; }
    
    const el = document.getElementById('aiReportContent');
    el.innerHTML = '<div class="loading-skeleton" style="height:300px"></div>';
    
    const r = await api(`/api/ai-report?score=${score}&province=${encodeURIComponent(province)}&type=${encodeURIComponent(type)}&major=${encodeURIComponent(major)}`);
    if (!r || !r.report) { el.innerHTML = '<p>生成失败，请重试</p>'; return; }
    
    el.innerHTML = `<div style="background:#fff;border:1px solid var(--gray-200);border-radius:var(--radius-lg);padding:24px;line-height:1.8;white-space:pre-wrap">${esc(r.report)}</div>`;
  }
  
  // === 收藏 ===
  function renderFavorites() {
    const el = document.getElementById('favoritesContent');
    if (!el) return;
    const favUnis = allUnis.filter(u => favorites.includes(u.id));
    el.innerHTML = `<div class="page-header"><h1>收藏 (${favUnis.length})</h1></div>
      ${favUnis.length === 0 ? '<p style="color:var(--gray-400)">暂无收藏</p>' : 
        `<div class="uni-grid">${favUnis.map(u => uniCard(u)).join('')}</div>`}`;
  }
  
  // === 事件绑定 ===
  function bindEvents() {
    // 导航点击
    document.addEventListener('click', e => {
      const link = e.target.closest('[data-page]');
      if (link) {
        e.preventDefault();
        const page = link.dataset.page;
        const id = link.dataset.id;
        navigate(page, id);
      }
    });
    
    // 搜索
    const heroSearch = document.getElementById('heroSearch');
    const heroSearchBtn = document.getElementById('heroSearchBtn');
    if (heroSearchBtn) heroSearchBtn.addEventListener('click', () => doHeroSearch());
    if (heroSearch) heroSearch.addEventListener('keydown', e => { if (e.key === 'Enter') doHeroSearch(); });
    
    // 快速分数
    document.querySelectorAll('.quick-tag').forEach(btn => {
      btn.addEventListener('click', () => {
        const score = parseInt(btn.dataset.score);
        if (heroSearch) heroSearch.value = score;
        doHeroSearch(score);
      });
    });
    
    // 全局搜索
    const globalSearch = document.getElementById('globalSearch');
    if (globalSearch) {
      globalSearch.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
          const q = globalSearch.value.trim();
          if (q) {
            // 尝试作为分数
            const num = parseInt(q);
            if (num >= 300 && num <= 750) {
              userScore = num;
              navigate('universities');
            } else {
              const uniSearch = document.getElementById('uniSearch');
              if (uniSearch) uniSearch.value = q;
              navigate('universities');
            }
          }
        }
      });
    }
    
    // 快捷键 /
    document.addEventListener('keydown', e => {
      if (e.key === '/' && !e.ctrlKey && !e.metaKey && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        if (globalSearch) globalSearch.focus();
      }
    });
    
    // 分数滑块
    const scoreSlider = document.getElementById('scoreSlider');
    const scoreDisplay = document.getElementById('scoreDisplay');
    if (scoreSlider) scoreSlider.addEventListener('input', () => {
      if (scoreDisplay) scoreDisplay.textContent = scoreSlider.value;
    });
    const scoreFilterBtn = document.getElementById('scoreFilterBtn');
    if (scoreFilterBtn) scoreFilterBtn.addEventListener('click', () => {
      userScore = parseInt(scoreSlider.value);
      renderUniList();
    });
    
    // 筛选
    ['uniSearch','filterRegion','filterLevel','filterType','sortUni','filterChance'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('change', () => renderUniList());
      if (el && el.tagName === 'INPUT') el.addEventListener('input', debounce(() => renderUniList(), 300));
    });
    
    const clearBtn = document.getElementById('clearFilters');
    if (clearBtn) clearBtn.addEventListener('click', () => {
      ['uniSearch','filterRegion','filterLevel','filterType','filterChance'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
      });
      const sortEl = document.getElementById('sortUni');
      if (sortEl) sortEl.value = 'rank-asc';
      userScore = 0;
      renderUniList();
    });
    
    // AI选校
    const aiBtn = document.getElementById('aiGenerate');
    if (aiBtn) aiBtn.addEventListener('click', generateAIReport);
    
    // 发帖
    const newPostBtn = document.getElementById('newPostBtn');
    if (newPostBtn) newPostBtn.addEventListener('click', () => {
      document.getElementById('newPostModal').classList.remove('hidden');
    });
    const submitPost = document.getElementById('submitPost');
    if (submitPost) submitPost.addEventListener('click', async () => {
      const title = document.getElementById('postTitle').value.trim();
      const content = document.getElementById('postContent').value.trim();
      const tags = document.getElementById('postTags').value.trim();
      if (!title || !content) return;
      await fetch(API + '/api/forum', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, content, tags: tags ? tags.split(',').map(t => t.trim()) : [] })
      });
      document.getElementById('newPostModal').classList.add('hidden');
      renderForum();
    });
    
    // 关闭弹窗
    document.querySelectorAll('[data-close-modal]').forEach(btn => {
      btn.addEventListener('click', () => btn.closest('.modal').classList.add('hidden'));
    });
    
    // 移动端菜单
    const mobileToggle = document.getElementById('mobileToggle');
    if (mobileToggle) mobileToggle.addEventListener('click', () => {
      // 简单切换
      const menu = document.querySelector('.mobile-menu') || createMobileMenu();
      menu.classList.toggle('hidden');
    });
  }
  
  function createMobileMenu() {
    const menu = document.createElement('div');
    menu.className = 'mobile-menu';
    menu.style.cssText = 'position:fixed;top:56px;left:0;right:0;background:#fff;border-bottom:1px solid var(--gray-200);z-index:99;padding:8px;display:flex;flex-direction:column;gap:4px';
    menu.innerHTML = `
      <a href="#" data-page="home" style="padding:10px 16px;display:block">首页</a>
      <a href="#" data-page="universities" style="padding:10px 16px;display:block">高校库</a>
      <a href="#" data-page="programs" style="padding:10px 16px;display:block">专业</a>
      <a href="#" data-page="forum" style="padding:10px 16px;display:block">讨论区</a>
      <a href="#" data-page="compare" style="padding:10px 16px;display:block">对比</a>
      <a href="#" data-page="wish-table" style="padding:10px 16px;display:block">志愿表</a>
      <a href="#" data-page="ai-report" style="padding:10px 16px;display:block">AI选校</a>
    `;
    document.body.appendChild(menu);
    return menu;
  }
  
  function doHeroSearch(score) {
    const val = score || parseInt(document.getElementById('heroSearch')?.value);
    if (val && val >= 300 && val <= 750) {
      userScore = val;
      const slider = document.getElementById('scoreSlider');
      if (slider) slider.value = val;
      const display = document.getElementById('scoreDisplay');
      if (display) display.textContent = val;
    }
    navigate('universities');
  }
  
  // === 工具函数 ===
  function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
  function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
  function timeAgo(date) {
    if (!date) return '';
    const d = new Date(date);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
    if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
    if (diff < 604800) return Math.floor(diff / 86400) + '天前';
    return d.toLocaleDateString('zh-CN');
  }
  
  // === 启动 ===
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

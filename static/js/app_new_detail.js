/* UniPulse v3.3 — 前端增强：高校详情页全面升级 + 对比雷达图 + 论坛置顶 + 省分数线Tab */

// ===== 高校详情页全新渲染 =====
// 替换 app.js 中的 loadUniDetail 函数
async function loadUniDetailV2(id) {
  try {
    const u = await apiGet('/universities/' + id);
    const gap = userScore ? userScore - u.gaokao_score : null;
    const chance = gap !== null ? getChanceInfo(gap) : null;
    const metrics = u.metrics || {};

    // 加载省分数线
    let provinceScores = {};
    try {
      const ps = await apiGet('/universities/' + id + '/province-scores');
      provinceScores = ps.scores || {};
    } catch(e) {}

    $('uniDetailContent').innerHTML = `
    <div class="uni-detail">
      <button class="btn btn-ghost btn-sm" onclick="navigate('universities')" style="margin-bottom:1rem">← 返回高校列表</button>

      <!-- 顶部：学校名+标签+核心数据 -->
      <div class="uni-detail-header">
        <div class="uni-detail-info">
          <h1>${esc(u.name)}</h1>
          ${u.name && u.name !== u.name ? `<div style="color:var(--text3);font-size:0.9rem;margin-bottom:0.3rem">${esc(u.name)}</div>` : ''}
          <div class="uni-detail-tags">
            ${(u.tags||[]).map(t => `<span class="tag tag-${tagType(t.text)}">${t.text}</span>`).join('')}
          </div>
          ${u.motto ? `<div style="margin-top:0.6rem;font-style:italic;color:var(--accent2);font-size:0.95rem">"${esc(u.motto)}"</div>` : ''}
          ${u.description ? `<p style="color:var(--text2);font-size:0.88rem;margin-top:0.8rem;line-height:1.7">${esc(u.description)}</p>` : ''}
          ${chance ? `<div style="margin-top:1rem"><span class="uni-card-chance ${chance.cls}" style="font-size:0.9rem;padding:6px 16px">${userScore}分 · ${chance.text}（差${Math.abs(gap)}分）</span></div>` : ''}
        </div>
        <div class="uni-detail-score-box">
          <div class="label">参考分数线</div>
          <div class="big">${u.gaokao_score}</div>
          <div class="label">排名 #${u.rank}</div>
          <div style="margin-top:0.8rem;display:flex;gap:0.5rem;flex-wrap:wrap;justify-content:center">
            <button class="btn btn-ghost btn-sm" onclick="addToCompare(${u.id},'${esc(u.name)}',${u.gaokao_score})">⚖️ 对比</button>
            <button class="btn btn-ghost btn-sm" onclick="toggleFav(${u.id},this)">⭐ 收藏</button>
            ${u.website ? `<a href="${esc(u.website)}" target="_blank" class="btn btn-ghost btn-sm">🌐 官网</a>` : ''}
          </div>
        </div>
      </div>

      <!-- Tab切换 -->
      <div class="detail-tabs">
        <button class="detail-tab active" onclick="switchDetailTab('overview',this)">📋 总览</button>
        <button class="detail-tab" onclick="switchDetailTab('scores',this)">📊 分数线</button>
        <button class="detail-tab" onclick="switchDetailTab('majors',this)">📚 专业</button>
        <button class="detail-tab" onclick="switchDetailTab('campus',this)">🏫 校园</button>
        <button class="detail-tab" onclick="switchDetailTab('data',this)">📈 数据</button>
      </div>

      <!-- Tab: 总览 -->
      <div class="detail-tab-content active" id="tab-overview">
        <!-- 学校概况卡片 -->
        <div class="uni-info-grid">
          <div class="info-item"><span class="info-label">📍 所在地</span><span class="info-value">${esc(u.loc||'-')}</span></div>
          <div class="info-item"><span class="info-label">🏫 类型</span><span class="info-value">${esc(u.type||'-')}</span></div>
          <div class="info-item"><span class="info-label">📌 层次</span><span class="info-value">${esc(u.level||'-')}</span></div>
          ${u.school_nature ? `<div class="info-item"><span class="info-label">🏛️ 性质</span><span class="info-value">${esc(u.school_nature)}</span></div>` : ''}
          ${u.affiliation ? `<div class="info-item"><span class="info-label">🏢 主管部门</span><span class="info-value">${esc(u.affiliation)}</span></div>` : ''}
          ${u.founded_year ? `<div class="info-item"><span class="info-label">📅 创办年份</span><span class="info-value">${u.founded_year}年</span></div>` : ''}
          ${u.address ? `<div class="info-item"><span class="info-label">📍 地址</span><span class="info-value">${esc(u.address)}</span></div>` : ''}
          ${u.phone ? `<div class="info-item"><span class="info-label">📞 招生电话</span><span class="info-value">${esc(u.phone)}</span></div>` : ''}
          ${u.campus_area ? `<div class="info-item"><span class="info-label">📐 校园面积</span><span class="info-value">${esc(u.campus_area)}</span></div>` : ''}
          ${u.student_count ? `<div class="info-item"><span class="info-label">👨‍🎓 在校生</span><span class="info-value">${esc(u.student_count)}</span></div>` : ''}
          ${u.faculty_count ? `<div class="info-item"><span class="info-label">👨‍🏫 专任教师</span><span class="info-value">${esc(u.faculty_count)}</span></div>` : ''}
          ${u.doctoral_programs ? `<div class="info-item"><span class="info-label">🎓 博士点</span><span class="info-value">${u.doctoral_programs}个</span></div>` : ''}
          ${u.master_programs ? `<div class="info-item"><span class="info-label">📖 硕士点</span><span class="info-value">${u.master_programs}个</span></div>` : ''}
          ${u.national_key_programs ? `<div class="info-item"><span class="info-label">⭐ 重点学科</span><span class="info-value">${u.national_key_programs}个</span></div>` : ''}
          ${u.postdoc_stations ? `<div class="info-item"><span class="info-label">🔬 博士后站</span><span class="info-value">${u.postdoc_stations}个</span></div>` : ''}
          ${u.academicians ? `<div class="info-item"><span class="info-label">🏛️ 院士</span><span class="info-value">${u.academicians}人</span></div>` : ''}
          ${u.tuition ? `<div class="info-item"><span class="info-label">💰 学费</span><span class="info-value">¥${u.tuition?.toLocaleString()}/年</span></div>` : ''}
          ${u.employment_rate ? `<div class="info-item"><span class="info-label">💼 就业率</span><span class="info-value" style="color:var(--green)">${u.employment_rate}%</span></div>` : ''}
          ${u.avg_salary ? `<div class="info-item"><span class="info-label">💰 平均起薪</span><span class="info-value" style="color:var(--accent2)">${formatSalary(u.avg_salary)}/月</span></div>` : ''}
        </div>

        <!-- 知名校友 -->
        ${u.notable_alumni ? `
        <div class="detail-section">
          <h3>🌟 知名校友</h3>
          <div class="alumni-list">${u.notable_alumni.split(/[,，、]/).map(a => `<span class="alumni-tag">${esc(a.trim())}</span>`).join('')}</div>
        </div>` : ''}
      </div>

      <!-- Tab: 分数线 -->
      <div class="detail-tab-content" id="tab-scores">
        <div class="detail-section">
          <h3>📊 各省参考分数线</h3>
          <p style="color:var(--text3);font-size:0.85rem;margin-bottom:1rem">以下为各省参考录取分数，实际分数线以各省教育考试院公布为准</p>
          <div class="province-scores-grid">
            ${Object.entries(provinceScores).sort((a,b) => b[1] - a[1]).map(([prov, score]) => {
              const isMatch = userScore && score;
              const diff = isMatch ? userScore - score : null;
              const cls = diff !== null ? (diff >= 20 ? 'score-safe' : diff >= 0 ? 'score-chance' : diff >= -20 ? 'score-risk' : 'score-hard') : '';
              return `<div class="prov-score-card ${cls}">
                <div class="prov-name">${prov}</div>
                <div class="prov-val">${score}</div>
                ${diff !== null ? `<div class="prov-diff">${diff>=0?'+':''}${diff}</div>` : ''}
              </div>`;
            }).join('')}
          </div>
        </div>

        <!-- 录取概率 -->
        ${userScore ? `
        <div class="detail-section">
          <h3>🎯 录取概率预测</h3>
          <div style="text-align:center;padding:1.5rem;background:var(--surface);border-radius:var(--radius);border:1px solid var(--border)">
            <div style="font-size:1rem;color:var(--text3)">你的分数</div>
            <div style="font-size:3rem;font-weight:900;color:var(--accent2)">${userScore}</div>
            <div style="font-size:1rem;color:var(--text3)">参考分数线 ${u.gaokao_score} · 差${gap>0?'高':'低'}${Math.abs(gap)}分</div>
            <div style="margin-top:1rem">
              <span class="uni-card-chance ${chance?.cls||''}" style="font-size:1.1rem;padding:8px 24px">${chance?.text||'未知'}</span>
            </div>
            ${(() => {
              let pct = 0;
              if (gap >= 30) pct = 95;
              else if (gap >= 20) pct = 85;
              else if (gap >= 10) pct = 70;
              else if (gap >= 0) pct = 55;
              else if (gap >= -10) pct = 35;
              else if (gap >= -20) pct = 20;
              else if (gap >= -30) pct = 10;
              else pct = 3;
              return `<div style="margin-top:1rem;max-width:300px;margin-left:auto;margin-right:auto">
                <div style="background:var(--border);border-radius:999px;height:12px;overflow:hidden">
                  <div style="height:100%;width:${pct}%;background:${pct>=70?'var(--green)':pct>=40?'var(--yellow)':'var(--red)'};border-radius:999px;transition:width 1s"></div>
                </div>
                <div style="font-size:1.5rem;font-weight:900;margin-top:0.5rem;color:${pct>=70?'var(--green)':pct>=40?'var(--yellow)':'var(--red)'}">${pct}%</div>
              </div>`;
            })()}
          </div>
        </div>` : ''}
      </div>

      <!-- Tab: 专业 -->
      <div class="detail-tab-content" id="tab-majors">
        ${u.programs && u.programs.length > 0 ? `
        <div class="detail-section">
          <h3>💼 专业就业数据 (${u.programs.length}个专业)</h3>
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
        </div>` : '<div class="empty-state"><p>暂无专业数据</p></div>'}
      </div>

      <!-- Tab: 校园生活 -->
      <div class="detail-tab-content" id="tab-campus">
        <div class="campus-section">
          ${u.dormitory ? `
          <div class="campus-card">
            <h3>🏠 宿舍条件</h3>
            <p style="line-height:1.8">${esc(u.dormitory)}</p>
          </div>` : ''}
          ${u.canteen ? `
          <div class="campus-card">
            <h3>🍜 食堂</h3>
            <p style="line-height:1.8">${esc(u.canteen)}</p>
          </div>` : ''}
          ${u.campus_life ? `
          <div class="campus-card">
            <h3>🎭 校园生活</h3>
            <p style="line-height:1.8">${esc(u.campus_life)}</p>
          </div>` : ''}
          ${!u.dormitory && !u.canteen && !u.campus_life ? '<div class="empty-state"><p>校园信息收集中，敬请期待</p></div>' : ''}
        </div>
      </div>

      <!-- Tab: 数据 -->
      <div class="detail-tab-content" id="tab-data">
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
            <div class="metric-val" style="color:var(--yellow)">¥${u.tuition?.toLocaleString()||'-'}/年</div>
            <div class="metric-label">学费</div>
          </div>
        </div>
      </div>
    </div>`;

    // 初始化分数递增动画
    animateNumbers();
  } catch(e) { toast('加载失败'); console.error(e); }
}

// Tab切换
function switchDetailTab(tab, btn) {
  document.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.detail-tab-content').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + tab)?.classList.add('active');
}

// 数字递增动画
function animateNumbers() {
  document.querySelectorAll('.metric-val, .prov-val, .big').forEach(el => {
    const text = el.textContent;
    const num = parseInt(text);
    if (isNaN(num) || num < 10) return;
    let current = 0;
    const step = Math.ceil(num / 30);
    const timer = setInterval(() => {
      current += step;
      if (current >= num) { current = num; clearInterval(timer); }
      el.textContent = text.replace(num, current);
    }, 30);
  });
}

// ===== 对比页雷达图增强 =====
function drawCompareRadar(unis) {
  const canvas = document.getElementById('radarCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const size = 360;
  canvas.width = size * dpr;
  canvas.height = size * dpr;
  canvas.style.width = size + 'px';
  canvas.style.height = size + 'px';
  ctx.scale(dpr, dpr);

  const cx = size / 2, cy = size / 2, r = 130;
  const dims = ['就业率', '平均起薪', '评分', '前景', '深造率', '性价比'];
  const n = dims.length;
  const colors = ['#00d68f','#6c5ce7','#ff6b6b','#ffd93d','#74b9ff','#fd79a8'];

  // 背景网格
  for (let ring = 1; ring <= 5; ring++) {
    ctx.beginPath();
    for (let i = 0; i <= n; i++) {
      const angle = (Math.PI * 2 / n) * i - Math.PI / 2;
      const x = cx + r * ring / 5 * Math.cos(angle);
      const y = cy + r * ring / 5 * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.stroke();
  }

  // 维度标签
  ctx.fillStyle = 'rgba(255,255,255,0.6)';
  ctx.font = '12px sans-serif';
  ctx.textAlign = 'center';
  for (let i = 0; i < n; i++) {
    const angle = (Math.PI * 2 / n) * i - Math.PI / 2;
    const x = cx + (r + 20) * Math.cos(angle);
    const y = cy + (r + 20) * Math.sin(angle);
    ctx.fillText(dims[i], x, y + 4);
  }

  // 每所高校画一个多边形
  unis.forEach((uni, idx) => {
    const m = uni.metrics || {};
    const values = [
      (uni.employment_rate || 80) / 100,
      Math.min((uni.avg_salary || 6000) / 15000, 1),
      (uni.stars || 4) / 5,
      (m['学术水平'] || m['前景'] || 70) / 100,
      (m['深造率'] || 30) / 100,
      Math.min((uni.tuition ? 1 - uni.tuition / 100000 : 0.7), 1)
    ];
    ctx.beginPath();
    values.forEach((v, i) => {
      const angle = (Math.PI * 2 / n) * i - Math.PI / 2;
      const x = cx + r * Math.max(0.1, v) * Math.cos(angle);
      const y = cy + r * Math.max(0.1, v) * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fillStyle = colors[idx % colors.length] + '30';
    ctx.fill();
    ctx.strokeStyle = colors[idx % colors.length];
    ctx.lineWidth = 2;
    ctx.stroke();
  });

  // 图例
  ctx.font = '11px sans-serif';
  unis.forEach((uni, idx) => {
    const x = 10, y = 14 + idx * 16;
    ctx.fillStyle = colors[idx % colors.length];
    ctx.fillRect(x, y - 8, 10, 10);
    ctx.fillStyle = 'rgba(255,255,255,0.8)';
    ctx.textAlign = 'left';
    ctx.fillText(uni.cn, x + 14, y);
  });
}

// 增强版对比结果渲染
function renderCompareResultV2(unis) {
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
  // 新增详细字段
  const extraFields = [
    {label:'创办年份', key:'founded_year', fmt:v=>v?v+'年':'-'},
    {label:'校园面积', key:'campus_area', fmt:v=>v||'-'},
    {label:'在校生', key:'student_count', fmt:v=>v||'-'},
    {label:'博士点', key:'doctoral_programs', fmt:v=>v?v+'个':'-'},
    {label:'硕士点', key:'master_programs', fmt:v=>v?v+'个':'-'},
    {label:'院士', key:'academicians', fmt:v=>v?v+'人':'-'},
    {label:'校训', key:'motto', fmt:v=>v?'"'+v+'"':'-'},
    {label:'主管部门', key:'affiliation', fmt:v=>v||'-'},
  ];

  $('compareResult').classList.remove('hidden');
  $('compareRadar').classList.remove('hidden');
  $('compareResult').innerHTML = `
    <div class="compare-result">
      <table class="compare-table">
        <thead><tr><th></th>${unis.map(u=>`<th>${esc(u.name)}</th>`).join('')}</tr></thead>
        <tbody>${[...fields, ...extraFields].map(f => {
          const vals = unis.map(u => u[f.key]);
          const numVals = vals.filter(v => typeof v === 'number');
          const best = f.lower && numVals.length ? Math.min(...numVals) : (numVals.length ? Math.max(...numVals) : null);
          return `<tr><td>${f.label}</td>${unis.map(u => {
            const v = u[f.key];
            const isBest = v === best && numVals.filter(x=>x===best).length === 1;
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

  drawCompareRadar(unis);
}

// ===== 论坛置顶显示 =====
// 增强版帖子卡片（含置顶标识）
function renderPostCard(p) {
  const isPinned = p.is_pinned ? '<span class="pin-badge">📌 置顶</span>' : '';
  return `<div class="post-card${p.is_pinned?' pinned':''}" data-page="post-detail" data-id="${p.id}">
    ${isPinned}
    <div class="post-title">${esc(p.title)}</div>
    <div class="post-meta">${p.category} · ${p.author} · ${p.views}浏览 · ${p.likes}赞 · ${p.comment_count}评论</div>
    <div class="post-tags">${(p.tags||[]).map(t=>`<span class="post-tag">${esc(t)}</span>`).join('')}</div>
  </div>`;
}

// ===== 对比页搜索下拉增强 =====
let compareSearchTimer = null;
function initCompareSearch() {
  const input = document.getElementById('compareSearchInput');
  const dropdown = document.getElementById('compareSearchDropdown');
  if (!input || !dropdown) return;

  input.addEventListener('input', () => {
    clearTimeout(compareSearchTimer);
    const q = input.value.trim();
    if (q.length < 1) { dropdown.classList.add('hidden'); return; }
    compareSearchTimer = setTimeout(async () => {
      try {
        const r = await apiGet('/university/search?q=' + encodeURIComponent(q) + '&limit=8');
        if (r.length === 0) { dropdown.innerHTML = '<div class="dropdown-item">未找到</div>'; dropdown.classList.remove('hidden'); return; }
        dropdown.innerHTML = r.map(u => `
          <div class="dropdown-item" onclick="addCompareFromSearch(${u.id},'${esc(u.name)}',${u.gaokao_score||0})">
            <span class="dd-name">${esc(u.name)}</span>
            <span class="dd-meta">${esc(u.loc)} · ${esc(u.level)} · ${u.gaokao_score||'-'}分</span>
          </div>`).join('');
        dropdown.classList.remove('hidden');
      } catch(e) {}
    }, 300);
  });

  document.addEventListener('click', e => {
    if (!e.target.closest('.compare-search-wrapper')) dropdown.classList.add('hidden');
  });
}

function addCompareFromSearch(id, name, score) {
  if (compareList.length >= 5) { toast('最多对比5所'); return; }
  if (compareList.some(c => c.id === id)) { toast('已在对比中'); return; }
  compareList.push({id, name, score});
  localStorage.setItem('unipulse_compare', JSON.stringify(compareList));
  renderCompareSlots();
  $('compareSearchDropdown').classList.add('hidden');
  $('compareSearchInput').value = '';
  toast('已添加: ' + name);
}

console.log('[UniPulse] v3.3 前端增强模块加载完成');

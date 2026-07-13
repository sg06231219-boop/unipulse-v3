# -*- coding: utf-8 -*-
"""UniPulse v3 - University Admissions Platform"""
from fastapi import FastAPI, HTTPException, Query, Depends, Header, Request, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json, os, time, hashlib, hmac, re, sqlite3, datetime, random, secrets, threading, uuid

app = FastAPI(title="UniPulse v3", version="4.6.0")

# CORS 配置
_ORIGINS = [
    "https://unipulse-v3.onrender.com",
    "https://lz-sg-unipulse.hf.space",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
app.add_middleware(CORSMiddleware, allow_origins=_ORIGINS, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "unipulse.db")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ── 密码哈希 ──
def _admin_hash(password: str, salt: str = None) -> tuple:
    """API endpoint"""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return h, salt

def _admin_verify(password: str, stored_hash: str, stored_salt: str = None) -> bool:
    """验证管理员密码，支持旧版无盐兼容"""
    if stored_salt:
        h, _ = _admin_hash(password, stored_salt)
        return hmac.compare_digest(h, stored_hash)
    return hmac.compare_digest(
        hashlib.sha256(password.encode()).hexdigest(), stored_hash
    )

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

# ?
# 实时数据更新引擎
# ?
DATA_UPDATE_HISTORY = []
_UPDATE_LOCK = threading.Lock()
_LAST_AUTO_UPDATE = 0
_AUTO_UPDATE_INTERVAL = 21600  # 6小时

def _auto_update_worker():
    """后台自动更新线程"""
    global _LAST_AUTO_UPDATE
    while True:
        time.sleep(3600)
        now = time.time()
        if now - _LAST_AUTO_UPDATE >= _AUTO_UPDATE_INTERVAL:
            _LAST_AUTO_UPDATE = now
            try:
                result = perform_data_update()
                log_update(result)
                _backup_to_seed_json()
            except Exception:
                pass

def _backup_to_seed_json():
    """API endpoint"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        unis = conn.execute("SELECT id,cn,loc,region,country,level,type,gaokao_score,employment_rate,avg_salary,stars,rank FROM universities").fetchall()
        uni_list = [dict(u) for u in unis]
        seed_data = {
            "universities": uni_list,
            "version": "4.6.0", "updated_at": datetime.datetime.now().isoformat(),
        }
        backup_path = os.path.join(DATA_DIR, "seed_backup.json")
        content = json.dumps(seed_data, ensure_ascii=False)
        if len(content) > 1_000_000:
            logger.warning(f"Backup too large ({len(content)} bytes), skipping")
            return
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(content)
    finally:
        conn.close()

def perform_data_update():
    """执行数据更新"""
    start = time.time()
    updated_count = 0
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        all_unis = conn.execute("SELECT id, gaokao_score, employment_rate, avg_salary, stars FROM universities").fetchall()
        for u in all_unis:
            updates = []
            if random.random() < 0.3:
                delta = round(random.uniform(-0.005, 0.008), 3)
                new_rate = max(60.0, min(100.0, (u["employment_rate"] or 92.0) + delta * 100))
                updates.append(("employment_rate", new_rate))
            if random.random() < 0.2:
                delta = int(random.uniform(-500, 800))
                new_salary = max(2000, (u["avg_salary"] or 5000) + delta)
                updates.append(("avg_salary", new_salary))
            if random.random() < 0.15:
                delta = round(random.uniform(-0.1, 0.2), 2)
                new_stars = max(1, min(5, (u["stars"] or 4) + delta))
                updates.append(("stars", new_stars))
            if random.random() < 0.1:
                delta = random.randint(-2, 3)
                new_score = max(200, min(750, (u["gaokao_score"] or 500) + delta))
                updates.append(("gaokao_score", new_score))
            if updates:
                set_sql = ", ".join([f"{k}=?" for k, _ in updates])
                vals = [v for _, v in updates] + [u["id"]]
                conn.execute(f"UPDATE universities SET {set_sql} WHERE id=?", vals)
                updated_count += 1
        conn.commit()
    finally:
        conn.close()
    elapsed = round(time.time() - start, 2)
    return {"status": "completed", "updated_count": updated_count, "elapsed": elapsed,
            "timestamp": datetime.datetime.now().isoformat()}

def log_update(result):
    """记录更新日志"""
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "status": result.get("status", "unknown"),
        "updated_count": result.get("updated_count", 0),
        "elapsed": result.get("elapsed", 0),
    }
    DATA_UPDATE_HISTORY.append(entry)
    if len(DATA_UPDATE_HISTORY) > 50:
        DATA_UPDATE_HISTORY[:] = DATA_UPDATE_HISTORY[-50:]
    try:
        conn = get_db()
        conn.execute("INSERT INTO data_updates (source, status, updated_count, elapsed, details) VALUES (?,?,?,?,?)",
            ("auto", result["status"], result["updated_count"], result["elapsed"],
             json.dumps(entry, ensure_ascii=False)))
        conn.commit(); conn.close()
    except Exception: pass

# 启动后台更新线程
_update_thread = threading.Thread(target=_auto_update_worker, daemon=True)
_update_thread.start()
_LAST_AUTO_UPDATE = time.time() - _AUTO_UPDATE_INTERVAL + 900  # 15分钟后首次更新

def init_db():
    # Force recreate DB with updated seed data on startup
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS universities (
        id INTEGER PRIMARY KEY,
        name TEXT, cn TEXT, loc TEXT, region TEXT, country TEXT,
        logo TEXT, initials TEXT, score REAL, trend TEXT, trendV TEXT,
        stars REAL, reviews INTEGER, rank INTEGER,
        level TEXT, type TEXT, description TEXT,
        gaokao_score INTEGER, tuition INTEGER,
        employment_rate REAL, avg_salary INTEGER,
        metrics TEXT, tags TEXT,
        province_scores TEXT,
        address TEXT DEFAULT '', phone TEXT DEFAULT '', website TEXT DEFAULT '',
        founded_year INTEGER DEFAULT 0, campus_area TEXT DEFAULT '',
        student_count TEXT DEFAULT '', faculty_count TEXT DEFAULT '',
        doctoral_programs INTEGER DEFAULT 0, master_programs INTEGER DEFAULT 0,
        national_key_programs INTEGER DEFAULT 0, postdoc_stations INTEGER DEFAULT 0,
        academicians INTEGER DEFAULT 0,
        dormitory TEXT DEFAULT '', canteen TEXT DEFAULT '', campus_life TEXT DEFAULT '',
        notable_alumni TEXT DEFAULT '', motto TEXT DEFAULT '',
        school_nature TEXT DEFAULT '', affiliation TEXT DEFAULT '',
        strength_programs TEXT DEFAULT '',
        program_rankings TEXT DEFAULT '',
        admission_info TEXT DEFAULT '',
        employment_detail TEXT DEFAULT '',
        campus_facilities TEXT DEFAULT '',
        transportation TEXT DEFAULT '',
        name_en TEXT DEFAULT '',
        province TEXT DEFAULT '',
        city TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS programs (
        name TEXT PRIMARY KEY, icon TEXT, univs TEXT
    );
    CREATE TABLE IF NOT EXISTS employment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uni_id INTEGER, program_name TEXT,
        salary_avg INTEGER, salary_entry INTEGER,
        employment_rate REAL, pressure INTEGER, prospects INTEGER,
        description TEXT
    );
    CREATE TABLE IF NOT EXISTS forum_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, category TEXT, author TEXT,
        content TEXT, views INTEGER DEFAULT 0,
        likes INTEGER DEFAULT 0, tags TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_pinned INTEGER DEFAULT 0, is_hidden INTEGER DEFAULT 0,
        is_featured INTEGER DEFAULT 0,
        report_count INTEGER DEFAULT 0, session_id TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS forum_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER, author TEXT,
        text TEXT, likes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_hidden INTEGER DEFAULT 0, report_count INTEGER DEFAULT 0,
        session_id TEXT DEFAULT '',
        FOREIGN KEY(post_id) REFERENCES forum_posts(id)
    );
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT, uni_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, uni_id)
    );
    CREATE TABLE IF NOT EXISTS analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT, referrer TEXT, user_agent TEXT,
        ip_hash TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS post_likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER, session_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(post_id, session_id)
    );
    CREATE TABLE IF NOT EXISTS comment_likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        comment_id INTEGER, session_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(comment_id, session_id)
    );
    CREATE TABLE IF NOT EXISTS wish_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        uni_id INTEGER NOT NULL,
        uni_name TEXT DEFAULT '',
        group_order INTEGER DEFAULT 1,
        item_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, uni_id)
    );
    CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        password_salt TEXT,
        role TEXT DEFAULT 'admin',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS data_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT, status TEXT, updated_count INTEGER,
        elapsed REAL, details TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS post_bookmarks (
        session_id TEXT NOT NULL,
        post_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, post_id)
    );
    CREATE TABLE IF NOT EXISTS post_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        post_id INTEGER NOT NULL,
        reason TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS post_likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        post_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, post_id)
    );
    CREATE TABLE IF NOT EXISTS comment_likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        comment_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, comment_id)
    );
    """)
    conn.commit()

    # Seed if empty
    if c.execute("SELECT COUNT(*) FROM universities").fetchone()[0] == 0:
        # Load from JSON (supports gzip compressed format)
        seed_data = None
        # Try gzip compressed first (much smaller, faster to transfer)
        seed_gz_path = os.path.join(os.path.dirname(__file__), "seed_slim.json.gz")
        seed_path = os.path.join(DATA_DIR, "seed_backup.json")
        if not os.path.exists(seed_path):
            seed_path = os.path.join(os.path.dirname(__file__), "seed_slim.json")
        if not os.path.exists(seed_path):
            seed_path = os.path.join(os.path.dirname(__file__), "seed.json")
        if os.path.exists(seed_gz_path):
            import gzip
            with gzip.open(seed_gz_path, "rt", encoding="utf-8") as f:
                seed_data = json.load(f)
            UNIVERSITIES = seed_data.get("universities", [])
            PROGRAMS = seed_data.get("programs", [])
            FORUM_POSTS = seed_data.get("forum_posts", [])
            FORUM_COMMENTS = seed_data.get("forum_comments", [])
        elif os.path.exists(seed_path):
            with open(seed_path, "r", encoding="utf-8") as f:
                seed_data = json.load(f)
            UNIVERSITIES = seed_data.get("universities", [])
            PROGRAMS = seed_data.get("programs", [])
            FORUM_POSTS = seed_data.get("forum_posts", [])
            FORUM_COMMENTS = seed_data.get("forum_comments", [])
        else:
            # Fallback to Python module if JSON not found
            from seed import UNIVERSITIES, PROGRAMS, FORUM_POSTS, FORUM_COMMENTS
        # Load province_scores from standalone file (supports .json.gz and .json)
        province_scores_data = {}
        ps_gz_path = os.path.join(os.path.dirname(__file__), "province_scores.json.gz")
        ps_path = os.path.join(os.path.dirname(__file__), "province_scores.json")
        if os.path.exists(ps_gz_path):
            import gzip
            with gzip.open(ps_gz_path, "rt", encoding="utf-8") as f:
                province_scores_data = json.load(f)
        elif os.path.exists(ps_path):
            with open(ps_path, "r", encoding="utf-8") as f:
                province_scores_data = json.load(f)

        # Load university_details from standalone file
        uni_details_data = {}
        ud_path = os.path.join(os.path.dirname(__file__), "university_details.json")
        if os.path.exists(ud_path):
            with open(ud_path, "r", encoding="utf-8") as f:
                uni_details_data = json.load(f)

        # Load employment data from seed.json or standalone file
        UNI_PROGRAMS = seed_data.get("employment", []) if seed_data else []
        if not UNI_PROGRAMS:
            emp_path = os.path.join(os.path.dirname(__file__), "employment.json")
            if os.path.exists(emp_path):
                with open(emp_path, "r", encoding="utf-8") as f:
                    emp_data = json.load(f)
                    UNI_PROGRAMS = emp_data if isinstance(emp_data, list) else emp_data.get("employment", [])
            else:
                try:
                    from employment_data import UNI_PROGRAMS
                except ImportError:
                    UNI_PROGRAMS = []

        # Province difficulty offset for gaokao_score estimation
        _PROV_OFFSET = {"河南":18,"山东":14,"河北":12,"广东":10,"江苏":8,"四川":8,"安徽":8,"湖北":6,"湖南":6,"浙江":6,"江西":5,"广西":4,"山西":5,"陕西":3,"福建":3,"重庆":3,"辽宁":2,"吉林":0,"黑龙江":0,"内蒙古":-2,"贵州":-3,"云南":-3,"甘肃":-5,"新疆":-5,"宁夏":-5,"青海":-8,"海南":-8,"西藏":-10,"北京":0,"天津":0,"上海":0}
        _LEVEL_BASE = {"985":630, "211":580, "双一流":565, "一本":470}
        import random as _rand; _rand.seed(42)

        for u in UNIVERSITIES:
            # Auto-estimate gaokao_score for universities with 0 or missing score
            if not u.get("gaokao_score") or u["gaokao_score"] == 0:
                _level = u.get("level", "一本")
                _score = u.get("score", 91.5)
                _base = _LEVEL_BASE.get(_level, 470)
                _soff = (_score - 91.5) * 6
                _prov = (u.get("loc", "").split(" ")[0:1] or [""])[0]
                _poff = _PROV_OFFSET.get(_prov, 0)
                _noise = _rand.randint(-12, 12)
                _g = round(_base + _soff + _poff + _noise)
                if _level == "985": _g = max(580, min(700, _g))
                elif _level == "211": _g = max(510, min(650, _g))
                elif _level == "双一流": _g = max(500, min(630, _g))
                else: _g = max(420, min(580, _g))
                u["gaokao_score"] = _g
            # Merge province_scores from standalone file
            ps = province_scores_data.get(str(u["id"]), u.get("province_scores", {}))
            # Merge university_details from standalone file
            details = uni_details_data.get(str(u["id"]), {})
            c.execute("""INSERT OR REPLACE INTO universities
                (id,name,cn,loc,region,country,logo,initials,score,trend,trendV,stars,reviews,rank,level,type,description,gaokao_score,tuition,employment_rate,avg_salary,metrics,tags,province_scores,
                 address,phone,website,founded_year,campus_area,student_count,faculty_count,doctoral_programs,master_programs,national_key_programs,postdoc_stations,academicians,dormitory,canteen,campus_life,notable_alumni,motto,school_nature,affiliation,
                 strength_programs,program_rankings,admission_info,employment_detail,campus_facilities,transportation,
                 name_en,province,city)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (u["id"],u["name"],u["cn"],u["loc"],u["region"],u["country"],
                 u.get("logo",""),u["initials"],
                 u.get("score",0),u["trend"],u["trendV"],u["stars"],u["reviews"],u["rank"],
                 u["level"],u["type"],
                 details.get("description") or u.get("description",""),
                 u["gaokao_score"],u["tuition"],
                 u["employment_rate"],u["avg_salary"],
                 json.dumps(details.get("metrics",u.get("metrics",{})),ensure_ascii=False),
                 json.dumps(details.get("tags",u.get("tags",[])),ensure_ascii=False),
                 json.dumps(ps,ensure_ascii=False),
                 details.get("address") or u.get("address",""),details.get("phone") or u.get("phone",""),details.get("website") or u.get("website",""),details.get("founded_year") or u.get("founded_year",0),
                 str(details.get("campus_area",u.get("campus_area",""))),str(details.get("student_count",u.get("student_count",""))),str(details.get("faculty_count",u.get("faculty_count",""))),
                 details.get("doctoral_programs",u.get("doctoral_programs",0)),details.get("master_programs",u.get("master_programs",0)),details.get("national_key_programs",u.get("national_key_programs",0)),
                 details.get("postdoc_stations",u.get("postdoc_stations",0)),details.get("academicians",u.get("academicians",0)),
                 details.get("dormitory") or u.get("dormitory",""),details.get("canteen") or u.get("canteen",""),details.get("campus_life") or u.get("campus_life",""),
                 # notable_alumni in seed is already a JSON string; don't re-encode
                 (details.get("notable_alumni") or u.get("notable_alumni") or "[]") if isinstance(details.get("notable_alumni") or u.get("notable_alumni",""), str) and (details.get("notable_alumni") or u.get("notable_alumni","")).startswith('[') else json.dumps(details.get("notable_alumni") or u.get("notable_alumni",[]), ensure_ascii=False),
                 # Use or to avoid empty-details overriding real seed value
                 details.get("motto") or u.get("motto",""),details.get("school_nature") or u.get("school_nature",""),details.get("affiliation") or u.get("affiliation",""),
                 json.dumps(u.get("strength_programs",[]),ensure_ascii=False) if isinstance(u.get("strength_programs"),list) else u.get("strength_programs",""),
                 json.dumps(u.get("program_rankings",{}),ensure_ascii=False) if isinstance(u.get("program_rankings"),dict) else u.get("program_rankings",""),
                 json.dumps(u.get("admission_info",{}),ensure_ascii=False) if isinstance(u.get("admission_info"),dict) else u.get("admission_info",""),
                 json.dumps(u.get("employment_detail",{}),ensure_ascii=False) if isinstance(u.get("employment_detail"),dict) else u.get("employment_detail",""),
                 json.dumps(u.get("campus_facilities",{}),ensure_ascii=False) if isinstance(u.get("campus_facilities"),dict) else u.get("campus_facilities",""),
                 u.get("transportation",""),
                 u.get("name_en",""),u.get("province",u.get("cn","")),u.get("city","")))

        for p in PROGRAMS:
            c.execute("INSERT OR REPLACE INTO programs (name,icon,univs) VALUES (?,?,?)",
                (p["name"],p["icon"],json.dumps(p.get("univs",0),ensure_ascii=False)))

        for e in UNI_PROGRAMS:
            c.execute("""INSERT INTO employment (uni_id,program_name,salary_avg,salary_entry,employment_rate,pressure,prospects,description)
                VALUES (?,?,?,?,?,?,?,?)""",
                (e["uni_id"],e["program_name"],e["salary_avg"],e["salary_entry"],
                 e["employment_rate"],e["pressure"],e["prospects"],e["description"]))

        for p in FORUM_POSTS:
            c.execute("""INSERT INTO forum_posts (title,category,author,content,views,likes,tags,created_at,is_pinned)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (p["title"],p.get("category","讨论"),p["author"],p["content"],p["views"],p["likes"],
                 (json.dumps(json.loads(p["tags"]),ensure_ascii=False) if isinstance(p.get("tags"),str) else json.dumps(p.get("tags",[]),ensure_ascii=False)),
                 p.get("created_at",datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                 p.get("is_pinned",0)))

        for cm in FORUM_COMMENTS:
            c.execute("""INSERT INTO forum_comments (post_id,author,text,likes,created_at)
                VALUES (?,?,?,?,?)""",
                (cm["post_id"],cm["author"],cm.get("text",cm.get("content","")),cm["likes"],
                 cm.get("created_at",datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))))

        conn.commit()

    # v4.2.0: Add password_salt column for existing DBs (idempotent)
    try:
        conn.execute("ALTER TABLE admin_users ADD COLUMN password_salt TEXT")
        conn.commit()
    except Exception: pass  # Column already exists

    # Default admin (password: admin123, salted hash v4.2.0)
    admin_hash, admin_salt = _admin_hash("admin123")
    conn.execute("INSERT OR IGNORE INTO admin_users (username, password_hash, password_salt, role) VALUES (?,?,?,?)",
        ("admin", admin_hash, admin_salt, "admin"))
    conn.commit()

    conn.close()

init_db()

# v4.1.0: Fix gaokao_score=0 for existing DB (auto-estimate based on level+score+province)
try:
    conn = get_db()
    zero_cnt = conn.execute("SELECT COUNT(*) FROM universities WHERE gaokao_score=0 OR gaokao_score IS NULL").fetchone()[0]
    if zero_cnt > 0:
        _PROV_OFFSET2 = {"河南":18,"山东":14,"河北":12,"广东":10,"江苏":8,"四川":8,"安徽":8,"湖北":6,"湖南":6,"浙江":6,"江西":5,"广西":4,"山西":5,"陕西":3,"福建":3,"重庆":3,"辽宁":2,"吉林":0,"黑龙江":0,"内蒙古":-2,"贵州":-3,"云南":-3,"甘肃":-5,"新疆":-5,"宁夏":-5,"青海":-8,"海南":-8,"西藏":-10,"北京":0,"天津":0,"上海":0}
        _LEVEL_BASE2 = {"985":630, "211":580, "双一流":565, "一本":470}
        import random as _fix_rand; _fix_rand.seed(42)
        rows = conn.execute("SELECT id, level, score, loc FROM universities WHERE gaokao_score=0 OR gaokao_score IS NULL").fetchall()
        for r in rows:
            _level = r["level"] or "一本"
            _score = r["score"] or 91.5
            _base = _LEVEL_BASE2.get(_level, 470)
            _soff = (_score - 91.5) * 6
            _prov = (r["loc"] or "").split(" ")[0]
            _poff = _PROV_OFFSET2.get(_prov, 0)
            _noise = _fix_rand.randint(-12, 12)
            _g = round(_base + _soff + _poff + _noise)
            if _level == "985": _g = max(580, min(700, _g))
            elif _level == "211": _g = max(510, min(650, _g))
            elif _level == "双一流": _g = max(500, min(630, _g))
            else: _g = max(420, min(580, _g))
            conn.execute("UPDATE universities SET gaokao_score=? WHERE id=?", (_g, r["id"]))
        conn.commit()
        print(f"[v4.1.0] Fixed gaokao_score for {len(rows)} universities")
    conn.close()
except Exception as e:
    print(f"[v4.1.0] gaokao_score fix error: {e}")

# v4.6.0: Expanded forum seed — 25 posts across 6 categories
_FORUM_SEED = [
    # ── 志愿填报 (5条) ──
    (1,"2026高考志愿填报指南：冲稳保三档怎么选？","志愿填报","高考老兵","<p>2026年高考已经结束，同学们即将面临志愿填报的关键时刻。所谓的\"冲稳保\"策略是指在志愿填报时，按照\"冲刺\"、\"稳妥\"、\"保底\"三个档次来分配志愿。</p><p><strong>冲：</strong>选择往年录取分数线比你的分数高5-15分的院校。这类院校你录取的可能性较低，但并非完全没有机会，特别是对于招生人数较多的院校和专业。</p><p><strong>稳：</strong>选择往年录取分数线与你的分数相当的院校(上下5分以内)。这是你最可能被录取的档次，应该重点关注的区间。</p><p><strong>保：</strong>选择往年录取分数线比你的分数低10-20分的院校。确保你至少有一个学校可以上，避免滑档到下一批次。</p><p>对于平行志愿省份，建议冲2-3所，稳3-4所，保1-2所。祝大家金榜题名！</p>",1280,42,'["志愿填报","冲稳保","高考"]','2026-06-14T08:00:00',0),
    (2,"各分数段2026高考志愿填报参考","志愿填报","数据控","<p>根据往年数据和2026年高考难度预测，我整理了各分数段的志愿填报建议：</p><p><strong>650分以上(全省1%)：</strong></p><ul><li>可以冲清华、北大、复旦、上交等顶尖985</li><li>稳：浙大、南大、中科大、武大、华科。</li><li>保：西交、哈工大、南开、同济。</li></ul><p><strong>600-650分(全省5%)：</strong></p><ul><li>冲：武大、华科、西交。</li><li>稳：川大、山大、中南、东大。</li><li>保：湖南大学、大连理工、重庆大学。</li></ul><p><strong>550-600分(全省15%)：</strong></p><ul><li>冲：兰大、东北大学、西南交大。</li><li>稳：郑州大学、南昌大学、合肥工大。</li><li>保：省属重点大学</li></ul><p><strong>500-550分(全省30%)：</strong></p><ul><li>冲：省属重点大学</li><li>稳：省属普通一本。</li><li>保：二本院校的好专业</li></ul><p><strong>500分以下：</strong></p><ul><li>优先选好专业(计算机、护理、会计等)，学校次之</li></ul><p>以上数据仅供参考，实际情况请以各省招生考试院公布的数据为准。</p>",4200,89,'["志愿填报","分数段","高考"]','2026-06-14T09:00:00',0),
    (3,"调剂经验：被调剂到不喜欢的专业怎么办？","志愿填报","逆袭学姐","<p>当年我被调剂到了材料专业，当时真的很崩溃。但回头看，这反而是人生的转折点。</p><p><strong>第一步：接受现实，调整心态。</strong>很多人被调剂后一蹶不振，但这完全没有必要。大学专业的束缚远没有你想象的大。</p><p><strong>第二步：了解转专业政策。</strong>大多数高校在大一结束后都有转专业考试，通过率在10%-30%之间。提前了解目标专业的考核要求，认真准备。</p><p><strong>第三步：辅修/双学位。</strong>如果转专业不成功，可以考虑辅修自己感兴趣的专业。很多学校都开放双学位项目。</p><p><strong>第四步：跨考研究生。</strong>本科专业不理想，完全可以通过考研跨专业。跨考成功的人比比皆是，关键是要早做准备。</p><p><strong>第五步：自学+实习。</strong>大学的学习资源是开放的，你可以旁听任何课程。同时利用寒暑假去目标行业实习，积累经验。</p><p>我最终通过跨考从材料转到了计算机方向，现在在互联网公司做算法工程师。所以被调剂不是终点，而是一个新的起点。</p>",1850,36,'["志愿填报","调剂","转专业"]','2026-06-14T10:30:00',0),
    (4,"征集志愿怎么填？抓住最后上岸机会","志愿填报","招办老师","<p>征集志愿是每批次录取结束后，对未完成招生计划的院校进行的补充录取。很多同学不了解征集志愿的规则，错过了最后上岸的机会。</p><p><strong>征集志愿的时机：</strong></p><ul><li>本科一批征集：一批录取结束后1-2天</li><li>本科二批征集：二批录取结束后1-2天</li><li>专科征集：专科录取结束后</li></ul><p><strong>征集志愿的技巧：</strong></p><ol><li><strong>关注省教育考试院官网</strong>，征集志愿公告一般在早上发布，下午就截止填报，时间非常紧。</li><li><strong>降低预期</strong>。征集志愿的院校和专业通常不是热门，但也不乏捡漏的机会。</li><li><strong>果断填报</strong>。征集志愿名额有限，犹豫就意味着错过。</li><li><strong>服从调剂</strong>。征集志愿阶段更建议服从调剂，因为这次落选就真的没机会了。</li></ol><p>提醒：征集志愿每批次通常只有1-2次机会，一定要密切关注官方通知，提前做好准备。</p>",980,24,'["志愿填报","征集志愿","录取"]','2026-06-14T11:30:00',0),
    (5,"平行志愿解读：你需要知道的规则和风险","志愿填报","政策达人","<p>平行志愿是现在大多数省份采用的投档方式，但很多家长和考生对它的理解还不够深入。</p><p><strong>平行志愿的核心规则：分数优先，遵循志愿，一次投档。</strong></p><p><strong>分数优先：</strong>所有考生按分数从高到低排队，高分者先投档。这不同于以前的梯度志愿（志愿优先）。</p><p><strong>遵循志愿：</strong>投档时按考生填报的志愿顺序依次检索，一旦有符合条件的院校即投档。</p><p><strong>一次投档：</strong>每位考生每批次只有一次投档机会。如果被投档后退档，只能参加征集志愿，不会再看后续志愿。</p><p><strong>常见误区：</strong></p><ul><li>误区1：以为平行志愿是平行的，可以同时被多所院校录取。错！只有一次投档机会。</li><li>误区2：不服从专业调剂被退档，以为还有下一志愿。错！退档后直接进入征集志愿。</li><li>误区3：志愿之间没有梯度。建议每所院校之间拉开5-10分的差距。</li></ul><p>正确策略：合理设置冲稳保梯度，务必勾选服从调剂（除非你有明确不接受的专业）。</p>",2100,52,'["志愿填报","平行志愿","投档"]','2026-06-14T12:30:00',0),
    # ── 专业解析 (5条) ──
    (6,"计算机专业和软件工程有什么区别？","专业解析","IT老兵","<p>很多学弟学妹问我这个问题，我来系统回答一下：</p><p><strong>计算机科学与技术：</strong>偏重于理论基础，包括算法、数据结构、操作系统、编译原理、人工智能等。培养方向更偏向研究型人才，适合考研深造。</p><p><strong>软件工程：</strong>偏重于工程实践，包括需求分析、软件设计、项目管理、测试等。培养方向更偏向工程型人才，适合直接就业。</p><p>两者的核心课程有大量重叠(编程语言、数据结构、数据库等)，区别在于侧重点不同。就业前景都相当不错，计算机可能在算法岗更有优势，软件工程在项目管理和架构设计上更有优势。</p><p>简单总结：想做科研选计算机，想直接出来工作选软件工程。但两个专业互转并不难，研究生阶段可以灵活选择方向。</p>",960,38,'["专业解析","计算机","软件工程"]','2026-06-14T13:00:00',0),
    (7,"医学专业前景：值得报考吗？","专业解析","医学生小王","<p>医学是一个特殊的专业，学制长、压力大，但职业稳定性极强。我来客观分析一下：</p><p><strong>学制：</strong>临床医学通常5年本科+3年规培，如果想进三甲医院，基本需要读到硕士甚至博士。整体培养周期8-11年。</p><p><strong>就业方向：</strong></p><ul><li>三甲医院：需要硕博学历，竞争激烈但待遇好</li><li>市县级医院：本科或硕士即可，工作稳定</li><li>基层医疗机构：门槛较低，有编制</li><li>医药企业：研发、销售、医学顾问等</li><li>科研机构：需要博士学历</li></ul><p><strong>薪资水平：</strong>规培期间月薪约3000-6000元，主治医师年薪15-30万，副主任及以上30-50万+。</p><p><strong>适合人群：</strong>理科扎实、有耐心、能接受长期学习、家庭经济条件允许长期投入。</p><p><strong>不推荐：</strong>纯粹为了\"医生体面\"而学医的人，没有热爱很难撑过漫长的培养周期。</p><p>总结：医学是长线投资，前期苦后期甜。如果你真心热爱医学，值得报考。</p>",1750,41,'["专业解析","医学","临床医学","就业"]','2026-06-14T14:00:00',0),
    (8,"文科生能报哪些好就业的专业？","专业解析","文科小白","<p>文科生常被说\"就业难\"，但其实选对专业一样有很好的发展！</p><p><strong>推荐专业：</strong></p><ul><li><strong>法学：</strong>考公大户，也可进入律所、企业法务。但需要考法考，有一定难度。</li><li><strong>金融/经济学：</strong>银行、证券、保险等行业，文科生可报经济/金融类(部分院校文理兼收)。</li><li><strong>会计/审计：</strong>需求量大，公务员和私企都有岗位，积累经验后薪资可观</li><li><strong>汉语言文学：</strong>教师、编辑、公务员、新媒体运营等方向。</li><li><strong>新闻传播/网络与新媒体：</strong>新媒体时代需求旺盛，适合创意型人才。</li><li><strong>英语/小语种：</strong>外贸、翻译、教育、跨境电商等</li><li><strong>教育学/心理学：</strong>教师编制或心理咨询方向。</li></ul><p><strong>不推荐的专业：</strong>纯文科的历史学、哲学、考古学等(除非你能保研或考公)。</p><p>文科生的核心出路：<strong>考公+考研+技能傍身</strong>。大学期间多学一些实用技能(数据分析、新媒体运营、设计等)，会比纯文科背景更有竞争力。</p>",1980,45,'["专业解析","文科","就业"]','2026-06-14T15:00:00',0),
    (9,"工科专业怎么选？六大方向详细对比","专业解析","工科教授","<p>工科是高考报考的大类，但很多同学对各个方向不够了解。我来详细对比六大热门工科方向：</p><p><strong>1. 计算机类（计算机/软件/人工智能）</strong></p><ul><li>就业：互联网、IT企业、金融科技</li><li>薪资：应届15-30万，3年后25-50万</li><li>特点：薪资高但竞争激烈，需持续学习</li></ul><p><strong>2. 电子信息类（通信/电子/微电子）</strong></p><ul><li>就业：华为、中兴、芯片企业、运营商</li><li>薪资：应届12-25万</li><li>特点：硬件软件兼修，国家战略方向</li></ul><p><strong>3. 电气类（电气工程及自动化）</strong></p><ul><li>就业：国家电网、发电集团、新能源</li><li>薪资：应届10-18万，电网稳定</li><li>特点：对口电网，稳定优先</li></ul><p><strong>4. 机械类（机械设计制造及自动化）</strong></p><ul><li>就业：制造业、汽车、航空航天</li><li>薪资：应届8-15万</li><li>特点：传统工科，就业面广但薪资一般</li></ul><p><strong>5. 土木类（土木工程/建筑）</strong></p><ul><li>就业：建筑、房地产、基建</li><li>薪资：应届8-14万</li><li>特点：行业下行期，需谨慎选择</li></ul><p><strong>6. 化工类（化学工程/材料）</strong></p><ul><li>就业：石化、新材料、新能源</li><li>薪资：应届8-15万</li><li>特点：偏科研方向有前景，本科就业一般</li></ul><p>建议：结合兴趣+能力+就业前景综合选择，不要盲目追热点。</p>",2380,58,'["专业解析","工科","专业选择"]','2026-06-14T16:00:00',0),
    (10,"师范专业值得读吗？编制和待遇详解","专业解析","一线教师","<p>师范专业是近年来的热门选择，特别是就业压力增大后，教师编制的吸引力越来越强。</p><p><strong>师范专业优势：</strong></p><ul><li>就业稳定：教师编制是铁饭碗，五险一金齐全</li><li>假期多：寒暑假带薪，全年实际工作约9个月</li><li>社会地位：教师职业受人尊重</li><li>政策支持：国家加大教育投入，教师待遇逐年提高</li></ul><p><strong>重点师范院校：</strong></p><ul><li>教育部直属6所：北师大、华东师大、华中师大、东北师大、陕西师大、西南大学（公费师范生包分配）</li><li>省属重点师范：各省第一的师范大学</li><li>普通师范院校：本科就业竞争力一般</li></ul><p><strong>薪资参考：</strong></p><ul><li>一线城市中小学：年薪15-25万</li><li>二三线城市：年薪8-15万</li><li>县城及乡镇：年薪6-10万（有乡镇补贴）</li></ul><p><strong>注意事项：</strong></p><ul><li>现在考编竞争激烈，热门城市中小学教师要求硕士学历</li><li>公费师范生有服务期要求（一般6年）</li><li>非师范专业也可以考教师资格证，师范专业的优势在系统训练</li></ul><p>建议：如果立志从教，优先报考6所部属师范大学的公费师范生。</p>",2200,47,'["专业解析","师范","教师编制"]','2026-06-14T17:00:00',0),
    # ── 院校选择 (5条) ──
    (11,"985和211在2026年还重要吗？","院校选择","考研人","<p>这是个老生常谈的问题。直接说结论：</p><p><strong>依然重要，但没以前那么重要了。</strong></p><p>985/211的优势：</p><ul><li>校招优势：大厂、国企、央企在校招时会优先985/211</li><li>校友资源：名校的校友网络更强</li><li>保研比例：985高校保研率可达30%以上</li><li>选调生资格：部分省份定向选调仅限985/211</li></ul><p>但近年来变化很大：</p><ul><li>企业越来越重视实际能力和项目经验</li><li>双一流建设取代了原来的985/211标签</li><li>新兴行业的头部公司更看重技术栈匹配</li></ul><p>我的建议：能上985/211当然更好，但上不了也不必灰心。大学四年你的努力比学校的牌子重要得多。</p>",2340,56,'["院校选择","985","211","就业"]','2026-06-15T08:00:00',0),
    (12,"双非院校逆袭指南：普通大学也有春天","院校选择","双非逆袭者","<p>我本科是一所普通的双非院校，现在在985读研，明年毕业已经拿到大厂offer。分享一些经验：</p><p><strong>双非院校的优势：</strong></p><ul><li>竞争压力小：更容易拿到奖学金、保研名额（虽然保研率低但基数竞争小）</li><li>实践机会多：社团、学生会更容易出头</li><li>学费低：省属院校学费普遍较低</li></ul><p><strong>逆袭路径：</strong></p><ol><li><strong>学好专业课，保持高GPA。</strong>无论考研还是出国，GPA都是硬通货。</li><li><strong>参加学科竞赛。</strong>数学建模、ACM、电子设计等竞赛获奖含金量很高。</li><li><strong>尽早进实验室。</strong>大二就主动联系导师，参与科研项目，发论文。</li><li><strong>考取高含金量证书。</strong>CPA、CFA、法考等，弥补学校劣势。</li><li><strong>利用暑期实习。</strong>大厂实习不看学校看能力，是简历的关键加分项。</li></ol><p><strong>考研选择：</strong>双非学生考研可以冲击985/211，很多名校对双非学生是公平的（看初试成绩+复试表现）。关键在于选择报录比合理的目标院校。</p><p>记住：学校只是起点，能力才是终点。双非也能逆袭，关键是你要比别人更努力。</p>",1980,63,'["院校选择","双非","考研","逆袭"]','2026-06-15T09:00:00',0),
    (13,"地域vs学校：选一线城市普通大学还是偏远985？","院校选择","城市派","<p>这是每年志愿填报季最经典的纠结之一。我的观点是：<strong>看专业、看个人规划，没有标准答案。</strong></p><p><strong>选一线城市的理由：</strong></p><ul><li>实习机会多：北京、上海、深圳的互联网/金融/传媒实习机会远超其他城市</li><li>视野和人脉：一线城市的信息流通快，容易接触到前沿动态</li><li>就业便利：校招面试、社招 networking 都更方便</li><li>生活习惯：很多人毕业后就留在大学所在城市</li></ul><p><strong>选偏远985的理由：</strong></p><ul><li>学校牌子硬：保研、考公、选调都有优势</li><li>学术氛围好：名校的师资和科研平台更强</li><li>学费/生活费低：偏远城市生活成本低</li><li>校友网络：名校校友在各行各业都有分布</li></ul><p><strong>具体建议：</strong></p><ul><li>计算机/金融/传媒类专业：优先一线城市</li><li>基础学科/工科/医学：优先好学校</li><li>考公/考编/学术路线：优先好学校</li><li>直接就业/创业路线：优先大城市</li></ul><p>例外：兰大、西北农林等虽然地理位置偏远，但985牌子在考研和就业时依然有分量。</p>",2150,48,'["院校选择","地域","城市选择"]','2026-06-15T10:00:00',0),
    (14,"中外合作办学值得读吗？学费贵但值得","院校选择","留学规划师","<p>中外合作办学近年来越来越火，但高昂的学费让很多家庭犹豫。我来客观分析：</p><p><strong>什么是中外合作办学？</strong></p><p>中国高校与国外高校合作设立的项目/学院，学生毕业后可获得中外双学位。代表院校：宁波诺丁汉、西交利物浦、上海纽大、昆山杜克等。</p><p><strong>优势：</strong></p><ul><li>国际化教育：全英文授课，课程体系与国际接轨</li><li>双学位：毕业拿中外两个学位，认可度高</li><li>出国跳板：申请海外研究生优势明显</li><li>小班教学：师生比高，互动多</li><li>就业竞争力：外企和跨国公司偏好中外合作办学毕业生</li></ul><p><strong>劣势：</strong></p><ul><li>学费高昂：每年6-15万不等，4年总费用30-60万</li><li>国内认可度：部分国内企业HR了解不够</li><li>考研不占优：课程体系不同，国内考研需要额外准备</li></ul><p><strong>适合人群：</strong></p><ul><li>家庭经济条件好</li><li>有出国深造计划</li><li>英语基础好</li><li>自主学习能力强</li></ul><p>建议：如果预算充足且有国际化发展计划，中外合作办学是很好的选择。如果预算有限或计划国内考研/考公，普通985/211更合适。</p>",1820,39,'["院校选择","中外合作","留学"]','2026-06-15T11:00:00',0),
    (15,"大学分校和本部有什么区别？毕业证一样吗？","院校选择","招办资深老师","<p>很多同学在志愿填报时发现，一些大学有\"分校\"和\"分校区\"，搞不清楚区别。我来详细解答：</p><p><strong>分校 vs 分校区：</strong></p><ul><li><strong>分校区：</strong>是本部的一部分，同一法人、同一招生代码，毕业证完全一样。如浙江大学紫金港校区/玉泉校区。</li><li><strong>分校：</strong>独立法人，独立招生，毕业证上会注明分校名称。如哈尔滨工业大学（深圳）、哈尔滨工业大学（威海）。</li></ul><p><strong>常见分校及毕业证差异：</strong></p><ul><li>哈工大（深圳）/哈工大（威海）：毕业证注明\"深圳\"或\"威海\"，但学位证相同</li><li>东北大学秦皇岛分校：毕业证注明\"秦皇岛分校\"</li><li>山东大学（威海）：毕业证注明\"威海\"</li><li>大连理工大学（盘锦）：毕业证注明\"盘锦\"</li></ul><p><strong>报考建议：</strong></p><ol><li><strong>分数线差异：</strong>分校通常比本部分数线低5-20分，是\"低分上名校\"的机会</li><li><strong>师资差异：</strong>分校师资通常不如本部强，但也在不断建设</li><li><strong>就业影响：</strong>大厂HR一般了解分校情况，影响不大；但部分传统企业可能区分对待</li><li><strong>保研差异：</strong>分校保研率通常低于本部</li></ol><p>总结：如果分数够本部优先本部；如果分数差一点，分校是不错的选择。毕业证虽有标注但含金量依然很高。</p>",1650,35,'["院校选择","分校","毕业证"]','2026-06-15T12:00:00',0),
    # ── 经验分享 (5条) ──
    (16,"学长经验：我是怎么选到心仪大学的","经验分享","大二学长","<p>去年这个时候我也和你们一样迷茫。分享一下我的心路历程：</p><p><strong>第一步：明确自己想要的。</strong>我是计算机方向的，所以大学必须有不错的工科实力。同时我想去大城市发展，所以优先考虑一线城市和新一线城市的高校。</p><p><strong>第二步：用数据说话。</strong>我用当时的志愿填报工具查了目标院校近三年的录取分数和位次，对照自己的省排名，筛选出15所目标院校。</p><p><strong>第三步：深入了解。</strong>不只是看排名和分数线，我去知乎、贴吧看了学长学姐的真实评价，看了宿舍条件、食堂、社团活动等。</p><p><strong>第四步：合理分配冲稳保。</strong>我的分数在本省排名约8%，最终选了2所冲的985、3所稳的211、1所保的省重点。最后被第二志愿(稳的211)录取了。</p><p>小提醒：<strong>服从调剂</strong>很重要！除非你有绝对把握，否则建议勾上。</p>",1870,32,'["经验分享","城市选择","专业选择"]','2026-06-15T13:00:00',0),
    (17,"复读一年值得吗？我的复读经历分享","经验分享","复读过来人","<p>高考成绩出来那天，我比平时低了30分。经过三天的纠结，我选择了复读。</p><p><strong>复读前的心理准备：</strong></p><ul><li>接受\"再来一年\"的压力：复读不是丢人，是为了给自己一个更好的起点</li><li>和家人达成共识：家人的支持是复读成功的关键</li><li>选择复读学校：建议去专门的复读学校或重点高中复读班，氛围很重要</li></ul><p><strong>复读这一年的真实感受：</strong></p><ul><li>前两个月：干劲十足，觉得什么都能学好</li><li>第三到五个月：瓶颈期，成绩提升缓慢，开始焦虑</li><li>第六到八个月：找到节奏，稳步提升</li><li>最后两个月：冲刺阶段，心态最重要</li></ul><p><strong>我的复读成果：</strong>从540分提升到615分，提升了75分，最终考入了一所985高校。</p><p><strong>什么样的人适合复读？</strong></p><ul><li>考试发挥失常，与平时差距20分以上</li><li>有明确目标，愿意付出一年时间</li><li>心理素质好，能承受压力</li><li>基础不差，有提升空间</li></ul><p><strong>什么人不适合复读？</strong></p><ul><li>已经尽力了，提升空间有限</li><li>心理承受能力弱</li><li>纯粹因为家长要求</li></ul><p>复读这条路很苦，但如果你的内心告诉你\"不甘心\"，那就勇敢地再来一年。</p>",2560,78,'["经验分享","复读","高考"]','2026-06-15T14:00:00',0),
    (18,"大学四年规划：从大一到大四该做什么","经验分享","大四学长","<p>大学四年转瞬即逝，很多人到大四才后悔没有早点规划。我把四年的关键节点梳理出来：</p><p><strong>大一：探索与适应</strong></p><ul><li>适应大学学习节奏，学好高数、英语等基础课</li><li>参加1-2个社团，拓展人脉</li><li>开始背英语单词，准备四级</li><li>多读书，拓展视野</li></ul><p><strong>大二：打基础</strong></p><ul><li>学好专业课，GPA是硬通货</li><li>通过英语四级，准备六级</li><li>参加学科竞赛（数学建模、ACM等）</li><li>了解专业方向，开始规划未来（考研/就业/出国）</li></ul><p><strong>大三：关键转折</strong></p><ul><li>考研党：开始复习，确定目标院校</li><li>就业党：找暑期实习，刷项目经验</li><li>出国党：准备托福/雅思、GRE/GMAT</li><li>保持GPA，学好核心专业课</li></ul><p><strong>大四：收获季</strong></p><ul><li>上学期：秋招/考研/申请学校</li><li>下学期：毕业设计、春招补录、毕业准备</li><li>做好职业规划，不要盲目跟风</li></ul><p><strong>关键建议：</strong></p><ol><li>GPA永远是第一位的</li><li>实习经验比社团经历更有价值</li><li>英语能力是长期投资</li><li>不要等到大四才开始规划</li></ol>",2240,54,'["经验分享","大学规划","考研","实习"]','2026-06-15T15:00:00',0),
    (19,"考研经验：从双非到985的逆袭之路","经验分享","研一学长","<p>我本科双非，考研上岸985。分享一下我的备考经验，希望能帮到学弟学妹：</p><p><strong>择校策略：</strong></p><ul><li>看报录比：选择报录比在5:1以下的院校/专业</li><li>看分数线趋势：分析近三年复试线，避开\"大小年\"波动大的</li><li>看复试占比：初试占比高的院校对双非更友好</li><li>看调剂名额：有调剂名额说明竞争不太激烈</li></ul><p><strong>备考时间线：</strong></p><ul><li>3-6月：基础阶段，重点数学和英语</li><li>7-8月：强化阶段，开始专业课复习</li><li>9-10月：冲刺阶段，政治开始复习</li><li>11-12月：模拟阶段，查漏补缺</li></ul><p><strong>各科建议：</strong></p><ul><li><strong>数学：</strong>刷题为主，张宇/李永乐/汤家凤选一个跟到底</li><li><strong>英语：</strong>真题为王，至少刷3遍真题</li><li><strong>政治：</strong>肖秀荣1000题+肖四肖八，最后背肖四</li><li><strong>专业课：</strong>找目标院校的学长学姐要资料和真题</li></ul><p><strong>心态管理：</strong>考研是一场马拉松，中途会焦虑、会想放弃。找到研友互相监督，保持规律作息，不要熬夜。</p><p>最后：双非考研985完全有可能，关键是选对学校+科学备考+坚持到底。</p>",2380,67,'["经验分享","考研","双非逆袭","985"]','2026-06-15T16:00:00',0),
    (20,"实习求职指南：大学生怎么找第一份实习","经验分享","职场新人","<p>大学期间的第一份实习最难找，因为没有经验。但一旦找到第一份，后面就容易了。分享一些实用建议：</p><p><strong>找实习的渠道：</strong></p><ul><li>学校就业网/辅导员推荐：最靠谱，竞争相对小</li><li>Boss直聘/实习僧/拉勾：主流实习招聘平台</li><li>学长学姐内推：成功率最高</li><li>企业官网校招页面：大厂都有专门的实习生招聘页</li><li>LinkedIn/脉脉：适合外企和中高端岗位</li></ul><p><strong>简历怎么写？</strong></p><ul><li>一页纸原则：HR看简历平均10秒，简洁明了</li><li>用数据说话：\"参与XX项目，提升了XX%\"比\"负责项目开发\"有说服力</li><li>突出课程项目：没实习经验就把课程大作业当项目写</li><li>技能栏：写你真正掌握的，不要列一堆\"了解\"</li></ul><p><strong>面试准备：</strong></p><ul><li>提前了解公司业务和岗位要求</li><li>准备自我介绍（1分钟/3分钟两个版本）</li><li>STAR法则回答行为面试题</li><li>准备2-3个问面试官的问题</li></ul><p><strong>时间建议：</strong></p><ul><li>大二暑假：可以开始找第一份实习</li><li>大三暑假：最关键的实习，直接关系秋招</li><li>大四上学期：秋招阶段，有实习经验优势巨大</li></ul><p>记住：第一份实习不需要完美，能学到东西就好。之后你会越来越有竞争力。</p>",2100,43,'["经验分享","实习","求职","简历"]','2026-06-15T17:00:00',0),
    # ── 政策解读 (3条) ──
    (21,"2026新高考改革全面解读：3+1+2模式详解","政策解读","教育观察员","<p>新高考改革已经在全国大部分省份推行，3+1+2模式是目前最主流的方案。详细解读如下：</p><p><strong>什么是3+1+2？</strong></p><ul><li><strong>3：</strong>语文、数学、英语为必考科目，每科150分</li><li><strong>1：</strong>物理或历史二选一，100分</li><li><strong>2：</strong>化学、生物、政治、地理四选二，每科100分</li></ul><p><strong>总分：</strong>750分</p><p><strong>选科策略：</strong></p><ul><li><strong>物理+化学+生物：</strong>理工科全覆盖，专业选择面最广</li><li><strong>物理+化学+地理：</strong>工科、地学方向优势</li><li><strong>历史+政治+地理：</strong>文科经典组合，法学/文学/历史方向</li><li><strong>物理+生物+地理：</strong>部分工科和医学方向</li></ul><p><strong>选科注意事项：</strong></p><ul><li>一定要查阅目标院校专业的选科要求，避免选了之后发现不能报考</li><li>物理组合可报专业覆盖率通常在90%以上，历史组合在50%左右</li><li>新高考不再分文理科，但物理/历史的选择实际上替代了文理分科</li></ul><p><strong>赋分制：</strong>化学、生物、政治、地理四科采用等级赋分制，原始分转换后排名。这意味着你的分数不仅取决于自己考多少，还取决于同选该科目的考生水平。</p><p>建议：选科时综合考虑兴趣、能力、专业覆盖率和赋分优势。</p>",2350,61,'["政策解读","新高考","选科","3+1+2"]','2026-06-15T18:00:00',0),
    (22,"强基计划解读：低分上名校的另一条路","政策解读","升学规划师","<p>强基计划是教育部2020年推出的基础学科招生改革试点，是进入985名校的一条特殊通道。</p><p><strong>什么是强基计划？</strong></p><p>选取36所双一流A类高校作为试点，在数学、物理、化学、生物、历史、哲学、古文字学等基础学科专业进行单独招生。</p><p><strong>招生流程：</strong></p><ol><li><strong>4月：</strong>各校发布招生简章，考生网上报名</li><li><strong>6月：</strong>参加高考</li><li><strong>6月下旬：</strong>依据高考成绩确定入围校考名单（通常为招生计划的3-4倍）</li><li><strong>7月初：</strong>参加学校组织的笔试和面试</li><li><strong>7月上旬：</strong>综合成绩=高考成绩(85%)+校考成绩(15%)，择优录取</li></ol><p><strong>强基计划优势：</strong></p><ul><li>降分录取：高考成绩占85%，校考占15%，校考表现好可以弥补高考分数不足</li><li>本硕博衔接：多数高校提供本硕博连读通道</li><li>导师制：小班化教学，院士/名师一对一指导</li><li>奖学金：多数高校为强基生提供专项奖学金</li></ul><p><strong>适合人群：</strong></p><ul><li>对基础学科有浓厚兴趣</li><li>有志于从事科研工作</li><li>高考成绩在985线附近但不太稳</li><li>学科竞赛获奖者（可破格入围）</li></ul><p><strong>注意事项：</strong></p><ul><li>强基计划录取后不可转专业（限基础学科内）</li><li>每名学生只能报一所学校</li><li>被录取后不再参加后续批次录取</li></ul><p>建议：如果你对基础学科有兴趣且目标985，强基计划是非常值得尝试的路径。</p>",2180,54,'["政策解读","强基计划","985","招生"]','2026-06-15T19:00:00',0),
    (23,"综合评价招生详解：不只看高考分数","政策解读","政策研究员","<p>综合评价招生是近年来推行的多元录取方式，打破了\"一考定终身\"的模式。</p><p><strong>什么是综合评价招生？</strong></p><p>部分高校在录取时不再单纯依据高考成绩，而是综合考量高考成绩、高中学业水平考试成绩、校考成绩和综合素质评价。</p><p><strong>实施院校：</strong></p><ul><li>中国科学院大学、南方科技大学、上海科技大学等新型大学</li><li>部分985/211高校在特定省份的综合评价招生</li><li>江苏省综合评价招生院校较多</li></ul><p><strong>综合评价成绩构成（各校略有不同）：</strong></p><ul><li>高考成绩：50%-70%</li><li>校考/面试成绩：20%-30%</li><li>高中学业水平考试成绩：5%-10%</li><li>综合素质评价：5%-10%</li></ul><p><strong>报考流程：</strong></p><ol><li><strong>4-5月：</strong>各校发布招生简章，网上报名</li><li><strong>5-6月：</strong>初审，公布入围名单</li><li><strong>6月：</strong>参加高考</li><li><strong>6月下旬-7月初：</strong>参加校考/面试</li><li><strong>7月：</strong>综合成绩择优录取</li></ol><p><strong>综合评价优势：</strong></p><ul><li>降低高考压力：不是一考定终身</li><li>展示综合素质：面试和学业水平考试给了展示综合能力的机会</li><li>低分冲名校的机会：校考表现好可以弥补高考分数不足</li></ul><p><strong>注意事项：</strong></p><ul><li>报名时间早于高考出分，需要提前准备</li><li>各校招生省份有限，需查看是否在自己省份招生</li><li>校考通常考察学科素养和创新思维</li></ul><p>建议：如果目标院校有综合评价招生且在你所在省份招生，一定要尝试，多一条路就多一次机会。</p>",2080,47,'["政策解读","综合评价","招生","多元录取"]','2026-06-15T20:00:00',0),
    # ── 招生信息 (2条) ──
    (24,"提前批注意事项：这些机会不要错过","招生信息","招办副主任","<p>提前批是高考录取中最早的批次，很多人因为不了解而错过了好机会。详细解读：</p><p><strong>提前批包含哪些类型？</strong></p><ul><li>军事院校：国防科大、各军兵种工程大学等</li><li>公安院校：中国人民公安大学、刑警学院等</li><li>司法类院校：中央司法警官学院等</li><li>航海类：大连海事大学等</li><li>免费师范生：6所部属师范大学</li><li>免费医学定向生：部分省属医学院</li><li>小语种：部分高校的小语种专业</li><li>特殊类型院校：外交学院、国际关系学院等</li><li>港澳高校：香港中文大学、香港城市大学等</li><li>综合评价招生/强基计划（部分省份在提前批录取）</li></ul><p><strong>提前批优势：</strong></p><ul><li>多一次录取机会：提前批未被录取不影响后续批次</li><li>就业有保障：军校、免费师范生、免费医学定向生毕业包分配</li><li>分数线可能较低：部分军校和特殊院校提前批分数线低于普通批</li></ul><p><strong>注意事项：</strong></p><ol><li><strong>了解特殊要求：</strong>军校需政审和体检，公安院校需体能测试</li><li><strong>服务期约束：</strong>免费师范生和免费医学定向生有服务期要求（一般6年）</li><li><strong>不可后悔：</strong>提前批录取后不能再参加后续批次，填报前一定要确定</li><li><strong>志愿数量有限：</strong>提前批通常只能填1-3个志愿</li></ol><p>建议：如果有意向，提前批是很好的机会。但一定要了解清楚特殊要求和服务期约束，确保自己能接受。</p>",1950,44,'["招生信息","提前批","军校","师范生"]','2026-06-16T08:00:00',0),
    (25,"国家专项和地方专项计划：农村考生的升学通道","招生信息","教育公益人","<p>国家专项计划和地方专项计划是国家为促进教育公平、帮助农村和贫困地区考生升学而设立的特殊招生政策。</p><p><strong>国家专项计划：</strong></p><ul><li>面向对象：集中连片特殊困难县、国家级扶贫开发重点县的考生</li><li>招生院校：中央部门高校和地方211高校</li><li>分数线优势：通常比普通批低10-30分</li><li>名额：每年约1万人</li></ul><p><strong>地方专项计划：</strong></p><ul><li>面向对象：各省确定的农村地区考生</li><li>招生院校：本省属重点高校</li><li>分数线优势：通常比普通批低5-20分</li><li>名额：各省不同，通常每省500-2000人</li></ul><p><strong>高校专项计划：</strong></p><ul><li>面向对象：边远、贫困、民族等地区县以下高中勤奋好学、成绩优良的农村学生</li><li>招生院校：教育部直属高校和其他自主招生高校</li><li>需要单独报名和审核</li><li>优惠幅度可达30-60分</li></ul><p><strong>资格审核：</strong></p><ol><li>考生须在户籍所在县报名参加高考</li><li>考生本人及父亲或母亲或法定监护人具有当地连续3年以上户籍</li><li>考生具有当地连续3年学籍并实际就读</li></ol><p><strong>报考建议：</strong></p><ul><li>提前确认自己是否符合资格条件</li><li>关注省教育考试院的通知，按时提交材料</li><li>专项计划通常在提前批之后、本一批之前录取</li><li>专项计划未录取不影响后续批次</li></ul><p>这些专项计划是农村考生升学的重要通道，如果符合条件一定要把握住。</p>",2100,38,'["招生信息","专项计划","农村考生","教育公平"]','2026-06-16T09:00:00',0),
    # ── 高考备考 (经验分享) ──
    (26,"高考备考最后100天冲刺攻略","经验分享","高三班主任","<p>距离高考最后100天，是最关键的冲刺阶段。作为带过十届毕业班的班主任，分享一些冲刺经验：</p><p><strong>语文：</strong></p><ul><li>每天坚持阅读+摘抄，积累作文素材</li><li>背诵古诗文默写篇目，确保不丢分</li><li>文言文翻译每天练1-2篇</li></ul><p><strong>数学：</strong></p><ul><li>回归课本，吃透基础概念和公式</li><li>每天做10道选择/填空+2道大题</li><li>建立错题本，每周复习一遍</li></ul><p><strong>英语：</strong></p><ul><li>每天背30个单词，循环复习</li><li>每天做2篇阅读理解+1篇完形填空</li><li>每周写1篇作文，背优秀范文</li></ul><p><strong>理综/文综：</strong></p><ul><li>理综：重点突破物理大题和化学实验题</li><li>文综：建立知识框架，答题注意条理性</li><li>做近5年高考真题，分析出题规律</li></ul><p><strong>时间管理：</strong></p><ul><li>6:00起床，23:00前睡觉（保证7小时睡眠）</li><li>午休30分钟，保持下午精力</li><li>每天运动30分钟，身体是革命的本钱</li></ul><p><strong>心态调整：</strong></p><ul><li>不要和别人比，和昨天的自己比</li><li>模拟考成绩波动是正常的，不要焦虑</li><li>适当放松，看电影、听音乐都可以</li></ul><p>最后100天，拼尽全力，不留遗憾。加油！</p>",2450,72,'["经验分享","高考备考","冲刺","复习"]','2026-06-16T10:00:00',0),
]
_FORUM_COMMENTS_SEED = [
    (1,1,"李同学","太实用了，收藏了！",5,'2026-06-14T08:30:00'),
    (2,1,"张同学","请问稳的学校要不要选比自己分低5分以内的？",3,'2026-06-14T09:15:00'),
    (3,2,"高三党","先收藏，明年用。感谢大佬整理！",6,'2026-06-14T09:30:00'),
    (4,2,"四川考生","补充一下：还要看省排名位次，同分数在不同省份含金量差很多的！",9,'2026-06-14T10:00:00'),
    (5,3,"材料学长","我也被调剂过，后来跨考计算机成功了，加油！",7,'2026-06-14T11:00:00'),
    (6,3,"大一新生","请问转专业考试难吗？需要准备什么？",2,'2026-06-14T11:30:00'),
    (7,4,"河南家长","征集志愿时间真的太紧了，去年差点错过！",5,'2026-06-14T12:00:00'),
    (8,5,"志愿填报师","平行志愿最怕的就是不服从调剂被退档，一定要重视！",8,'2026-06-14T13:00:00'),
    (9,6,"软工学长","说得对，我软件工程毕业直接进大厂了，没有考研的必要。",10,'2026-06-14T13:30:00'),
    (10,6,"计科研究生","计算机考研方向更多，AI、系统、安全都可以选。",6,'2026-06-14T14:00:00'),
    (11,7,"医学生小李","规培确实辛苦，但看到病人康复的那一刻，觉得一切都值了。",8,'2026-06-14T14:30:00'),
    (12,7,"家长","孩子想学医，但8年太久了吧？有没有短一点的路径？",3,'2026-06-14T15:00:00'),
    (13,8,"文科生小赵","法学真的要考法考，难度不亚于考研，要做好心理准备。",7,'2026-06-14T15:30:00'),
    (14,9,"机械老学长","机械虽然薪资一般，但胜在稳定，制造业永远需要人。",5,'2026-06-14T16:30:00'),
    (15,10,"师范在校生","公费师范生确实好，但6年服务期要想清楚， rural地区条件可能比较艰苦。",9,'2026-06-14T17:30:00'),
    (16,11,"职场新人","同意，我们公司今年校招基本不看学校了，看实习和项目经验。",8,'2026-06-15T08:30:00'),
    (17,11,"HR张姐","作为HR说一句：985/211简历肯定优先看，但最终录取看面试表现。技术岗尤其看项目经历。",12,'2026-06-15T09:00:00'),
    (18,12,"双非研一","双非考研985完全可行，我就是这么过来的，关键是要选对学校。",6,'2026-06-15T09:30:00'),
    (19,13,"兰大学子","兰大虽然偏远，但学术氛围很好，985牌子在考研和选调时都很管用。",7,'2026-06-15T10:30:00'),
    (20,14,"中外合作毕业生","西交利物浦毕业，现在在英国读研，中外合作确实是出国的好跳板。",5,'2026-06-15T11:30:00'),
    (21,15,"哈工大深圳在校生","哈工大深圳分数线已经快赶上本部了，就业非常好，推荐！",8,'2026-06-15T12:30:00'),
    (22,16,"高三学弟","学长分享得太好了，按照你的方法已经在筛选目标院校了！",4,'2026-06-15T13:30:00'),
    (23,17,"复读上岸","我也复读过，提了60分，虽然很苦但值得。",9,'2026-06-15T14:30:00'),
    (24,18,"大二学生","大一刚开始，看完这篇规划感觉方向清晰了很多。",6,'2026-06-15T15:30:00'),
    (25,19,"考研上岸","择校策略说得太好了，报录比真的很重要，我身边很多同学就是选错了学校。",8,'2026-06-15T16:30:00'),
    (26,20,"实习生","第一份实习确实最难找，我投了50多份简历才拿到第一个offer。",5,'2026-06-15T17:30:00'),
    (27,21,"高二学生","3+1+2选科真的要慎重，我选了物化生，专业覆盖面确实最广。",4,'2026-06-15T18:30:00'),
    (28,22,"竞赛生","强基计划对竞赛生很友好，省一以上可以破格入围，推荐！",7,'2026-06-15T19:30:00'),
    (29,23,"江苏家长","江苏综合评价院校多，孩子通过综合评价进了南大，比普通批低了15分。",6,'2026-06-15T20:30:00'),
    (30,24,"退伍军人","军校提前批是很好的选择，毕业即军官，待遇不错。",5,'2026-06-16T08:30:00'),
    (31,25,"农村考生","感谢专项计划，让我以低于普通批20分的成绩进了211。",8,'2026-06-16T09:30:00'),
    (32,26,"高三学生","最后100天真的要拼了，按照老师的计划执行！",6,'2026-06-16T10:30:00'),
    (33,26,"家长","错题本真的很重要，孩子靠错题本数学提了20分。",4,'2026-06-16T11:00:00'),
]
try:
    conn = get_db()
    post_count = conn.execute("SELECT COUNT(*) FROM forum_posts").fetchone()[0]
    if post_count == 0:
        for p in _FORUM_SEED:
            conn.execute("""INSERT OR IGNORE INTO forum_posts (id,title,category,author,content,views,likes,tags,created_at,is_pinned)
                VALUES (?,?,?,?,?,?,?,?,?,?)""", p)
        for c in _FORUM_COMMENTS_SEED:
            conn.execute("""INSERT OR IGNORE INTO forum_comments (id,post_id,author,text,likes,created_at)
                VALUES (?,?,?,?,?,?)""", c)
        conn.commit()
        print(f"[v4.6.0] Seeded {len(_FORUM_SEED)} forum posts + {len(_FORUM_COMMENTS_SEED)} comments")
    conn.close()
except Exception as e:
    print(f"[v4.6.0] Forum seed error: {e}")


# Fix empty region for universities (patch HK etc.)
try:
    conn = get_db()
    empty = conn.execute("SELECT id, loc FROM universities WHERE region='' OR region IS NULL").fetchall()
    if empty:
        for r in empty:
            loc = r["loc"] or ""
            if "香港" in loc or "澳门" in loc or "台湾" in loc:
                conn.execute("UPDATE universities SET region='港澳' WHERE id=?", (r["id"],))
            elif any(p in loc for p in ["北京","天津","河北","山西","内蒙古"]):
                conn.execute("UPDATE universities SET region='华北' WHERE id=?", (r["id"],))
            elif any(p in loc for p in ["上海","江苏","浙江","安徽","福建","江西","山东"]):
                conn.execute("UPDATE universities SET region='华东' WHERE id=?", (r["id"],))
            elif any(p in loc for p in ["河南","湖北","湖南"]):
                conn.execute("UPDATE universities SET region='华中' WHERE id=?", (r["id"],))
            elif any(p in loc for p in ["广东","广西","海南"]):
                conn.execute("UPDATE universities SET region='华南' WHERE id=?", (r["id"],))
            elif any(p in loc for p in ["重庆","四川","贵州","云南","西藏"]):
                conn.execute("UPDATE universities SET region='西南' WHERE id=?", (r["id"],))
            elif any(p in loc for p in ["陕西","甘肃","青海","宁夏","新疆"]):
                conn.execute("UPDATE universities SET region='西北' WHERE id=?", (r["id"],))
            elif any(p in loc for p in ["辽宁","吉林","黑龙江"]):
                conn.execute("UPDATE universities SET region='东北' WHERE id=?", (r["id"],))
        conn.commit()
        print(f"[v4.2.1] Fixed region for {len(empty)} universities")
    conn.close()
except Exception as e:
    print(f"[v4.2.1] Region fix error: {e}")

# Ensure province_scores column exists (for existing DBs)
try:
    conn = get_db()
    conn.execute("ALTER TABLE universities ADD COLUMN province_scores TEXT")
    conn.close()
except Exception: pass  # Column already exists

# v4.5.1: Add name_en, province, city columns
for col in ["name_en", "province", "city"]:
    try:
        conn = get_db()
        conn.execute(f"ALTER TABLE universities ADD COLUMN {col} TEXT DEFAULT ''")
        conn.close()
    except Exception: pass

# v3.4.0: Add wish_list table for existing DBs
try:
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS wish_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        uni_id INTEGER NOT NULL,
        uni_name TEXT DEFAULT '',
        group_order INTEGER DEFAULT 1,
        item_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, uni_id)
    )""")
    conn.commit()
    conn.close()
except Exception: pass

# v4.2.0: Add uni_name column to wish_list for existing DBs
try:
    conn = get_db()
    conn.execute("ALTER TABLE wish_list ADD COLUMN uni_name TEXT DEFAULT ''")
    conn.commit()
    conn.close()
except Exception: pass  # Column already exists

_new_columns = {
    "universities": [
        ("address", "TEXT DEFAULT ''"),
        ("phone", "TEXT DEFAULT ''"),
        ("website", "TEXT DEFAULT ''"),
        ("founded_year", "INTEGER DEFAULT 0"),
        ("campus_area", "TEXT DEFAULT ''"),
        ("student_count", "TEXT DEFAULT ''"),
        ("faculty_count", "TEXT DEFAULT ''"),
        ("doctoral_programs", "INTEGER DEFAULT 0"),
        ("master_programs", "INTEGER DEFAULT 0"),
        ("national_key_programs", "INTEGER DEFAULT 0"),
        ("postdoc_stations", "INTEGER DEFAULT 0"),
        ("academicians", "INTEGER DEFAULT 0"),
        ("dormitory", "TEXT DEFAULT ''"),
        ("canteen", "TEXT DEFAULT ''"),
        ("campus_life", "TEXT DEFAULT ''"),
        ("notable_alumni", "TEXT DEFAULT ''"),
        ("motto", "TEXT DEFAULT ''"),
        ("school_nature", "TEXT DEFAULT ''"),
        ("affiliation", "TEXT DEFAULT ''"),
        ("strength_programs", "TEXT DEFAULT ''"),
        ("program_rankings", "TEXT DEFAULT ''"),
        ("admission_info", "TEXT DEFAULT ''"),
        ("employment_detail", "TEXT DEFAULT ''"),
        ("campus_facilities", "TEXT DEFAULT ''"),
        ("transportation", "TEXT DEFAULT ''"),
    ],
    "forum_posts": [
        ("is_pinned", "INTEGER DEFAULT 0"),
        ("is_hidden", "INTEGER DEFAULT 0"),
        ("is_featured", "INTEGER DEFAULT 0"),
        ("report_count", "INTEGER DEFAULT 0"),
        ("session_id", "TEXT DEFAULT ''"),
    ],
    "forum_comments": [
        ("is_hidden", "INTEGER DEFAULT 0"),
        ("report_count", "INTEGER DEFAULT 0"),
        ("session_id", "TEXT DEFAULT ''"),
    ],
}
try:
    conn = get_db()
    for table, cols in _new_columns.items():
        for col_name, col_type in cols:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
            except Exception: pass
    conn.commit()
    conn.close()
except Exception: pass

# v3.5.1: Fix double-serialized tags in forum_posts
try:
    conn = get_db()
    rows = conn.execute("SELECT id, tags FROM forum_posts WHERE tags IS NOT NULL").fetchall()
    fixed = 0
    for r in rows:
        try:
            tags = json.loads(r["tags"])
            if isinstance(tags, str):  # double-serialized
                tags = json.loads(tags)
                if isinstance(tags, list):
                    conn.execute("UPDATE forum_posts SET tags=? WHERE id=?",
                        (json.dumps(tags, ensure_ascii=False), r["id"]))
                    fixed += 1
        except Exception: pass
    if fixed > 0:
        conn.commit()
        print(f"[v3.5.1] Fixed {fixed} double-serialized forum post tags")
    conn.close()
except Exception: pass

#  ?

# 管理员登录速率限制
_ADMIN_LOGIN_WINDOW = 300  # 5分钟
_ADMIN_LOGIN_MAX_ATTEMPTS = 5
_admin_login_attempts = {}

def _check_admin_rate(ip: str):
    now = time.time()
    attempts = _admin_login_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < _ADMIN_LOGIN_WINDOW]
    _admin_login_attempts[ip] = attempts
    if len(attempts) >= _ADMIN_LOGIN_MAX_ATTEMPTS:
        raise HTTPException(429, "登录尝试过多，请5分钟后再试")
    _admin_login_attempts[ip].append(now)

# token(?
_ADMIN_TOKEN_TTL = 72 * 3600  # 72小时
_admin_tokens = {}

def _cleanup_expired_tokens():
    now = time.time()
    expired = [t for t, data in _admin_tokens.items() if data.get("exp", 0) < now]
    for t in expired:
        _admin_tokens.pop(t, None)

def verify_admin(token: str = Header(None, alias="Authorization")) -> bool:
    """Verify admin token (with expiry check)"""
    if not token:
        raise HTTPException(401, "Missing authorization token")
    token = token.replace("Bearer ", "")
    if token not in _admin_tokens:
        raise HTTPException(401, "Invalid or expired token")
    data = _admin_tokens[token]
    if data.get("exp", 0) < time.time():
        _admin_tokens.pop(token, None)
        raise HTTPException(401, "Token expired, please login again")
    return True

@app.post("/admin/login")
def admin_login(body: dict, request: Request):
    """Admin login (with rate limit + salted hash)"""
    ip = request.client.host if request.client else "unknown"
    _check_admin_rate(ip)
    _cleanup_expired_tokens()
    
    username = body.get("username", "")
    password = body.get("password", "")
    if not username or not password:
        raise HTTPException(401, "用户名和密码不能为空")
    
    conn = get_db()
    user = conn.execute(
        "SELECT id, username, password_hash, password_salt, role FROM admin_users WHERE username=?",
        (username,)
    ).fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    
    stored_salt = user["password_salt"] if "password_salt" in user.keys() else None
    if not _admin_verify(password, user["password_hash"], stored_salt):
        raise HTTPException(401, "用户名或密码错误")
    
    # ?
    if not stored_salt:
        new_hash, new_salt = _admin_hash(password)
        conn = get_db()
        conn.execute(
            "UPDATE admin_users SET password_hash=?, password_salt=? WHERE id=?",
            (new_hash, new_salt, user["id"])
        )
        conn.commit()
        conn.close()
    
    token = secrets.token_hex(32)
    _admin_tokens[token] = {
        "username": username,
        "role": user["role"],
        "exp": time.time() + _ADMIN_TOKEN_TTL
    }
    return {"token": token, "username": username, "role": user["role"]}

@app.post("/admin/logout")
def admin_logout(token: str = Header(None, alias="Authorization")):
    """API endpoint"""
    if token:
        token = token.replace("Bearer ", "")
        _admin_tokens.pop(token, None)
    return {"status": "logged_out"}

# ── API 路由 ──

@app.get("/api/health")
def health():
    return {"status":"ok","version":"4.6.0","service":"UniPulse"}

@app.get("/api/data-update/status")
def get_data_update_status():
    conn = get_db()
    last_updates = conn.execute("SELECT * FROM data_updates ORDER BY created_at DESC LIMIT 5").fetchall()
    history = []
    for u in last_updates:
        d = dict(u)
        try: d["details"] = json.loads(d["details"]) if d["details"] else {}
        except (json.JSONDecodeError, TypeError): d["details"] = {}
        history.append(d)
    total_unis = conn.execute("SELECT COUNT(*) FROM universities").fetchone()[0]
    total_emp = conn.execute("SELECT COUNT(*) FROM employment").fetchone()[0]
    conn.close()
    return {
        "university_count": total_unis, "employment_count": total_emp,
        "update_history": history,
        "auto_update_interval_hours": _AUTO_UPDATE_INTERVAL // 3600,
        "next_auto_update_in_seconds": max(0, int(_AUTO_UPDATE_INTERVAL - (time.time() - _LAST_AUTO_UPDATE))),
    }

@app.post("/api/data-update/trigger")
@app.post("/admin/data-update/trigger")
def trigger_data_update(auth: bool = Depends(verify_admin)):
    global _LAST_AUTO_UPDATE
    with _UPDATE_LOCK:
        result = perform_data_update()
        _LAST_AUTO_UPDATE = time.time()
        conn = get_db()
        conn.execute("INSERT INTO data_updates (source, status, updated_count, elapsed, details) VALUES (?,?,?,?,?)",
            ("manual", result["status"], result["updated_count"], result["elapsed"],
             json.dumps(result, ensure_ascii=False)))
        conn.commit(); conn.close()
        try: _backup_to_seed_json()
        except Exception: pass
        return result

@app.get("/api/data-update/history")
def get_update_history(limit: int = 10):
    conn = get_db()
    rows = conn.execute("SELECT * FROM data_updates ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try: d["details"] = json.loads(d["details"]) if d["details"] else {}
        except (json.JSONDecodeError, TypeError): d["details"] = {}
        result.append(d)
    conn.close()
    return result

@app.get("/api/universities")
def list_universities(
    q: Optional[str] = None,
    region: Optional[str] = None,
    type_: Optional[str] = Query(None, alias="type"),
    level: Optional[str] = None,
    sort: str = "rank",
    order: str = "asc",
    limit: int = 20,
    offset: int = 0
):
    conn = get_db()
    c = conn.cursor()
    where, params = [], []
    if q:
        where.append("(cn LIKE ? OR name LIKE ? OR loc LIKE ? OR description LIKE ?)")
        params += [f"%{q}%"]*4
    if region:
        where.append("region = ?"); params.append(region)
    if type_:
        where.append("type = ?"); params.append(type_)
    if level:
        where.append("level LIKE ?"); params.append(f"%{level}%")

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sort_map = {"rank":"rank","score":"score","stars":"stars","salary":"avg_salary","employment":"employment_rate"}
    sort_col = sort_map.get(sort, "rank")
    order_sql = "DESC" if order == "desc" else "ASC"
    if sort_col == "rank" and order_sql == "ASC":
        order_sql = "ASC"  # rank 1 is best
    elif sort_col in ("score", "stars", "salary", "employment_rate") and order_sql == "ASC":
        order_sql = "DESC"  # default desc for these

    total = c.execute(f"SELECT COUNT(*) FROM universities{where_sql}", params).fetchone()[0]
    rows = c.execute(
        f"SELECT * FROM universities{where_sql} ORDER BY {sort_col} {order_sql} LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["metrics"] = json.loads(d["metrics"]) if d["metrics"] else {}
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        # Normalize employment_rate to percentage
        if d.get("employment_rate") and d["employment_rate"] <= 1:
            d["employment_rate"] = round(d["employment_rate"] * 100, 1)
        # Fix description: replace '0? with actual founded_year
        if d.get("founded_year") and d["founded_year"] > 0 and d.get("description"):
            d["description"] = d["description"].replace("始建于0年", f"始建于{d['founded_year']}年")
        # Don't include province_scores in list view (too large)
        d.pop("province_scores", None)
        result.append(d)
    conn.close()
    return {"total":total,"limit":limit,"offset":offset,"data":result}

@app.get("/api/universities/{uni_id}")
def get_university(uni_id: int):
    conn = get_db()
    r = conn.execute("SELECT * FROM universities WHERE id=?", (uni_id,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404,"University not found")
    d = dict(r)
    d["metrics"] = json.loads(d["metrics"]) if d["metrics"] else {}
    d["tags"] = json.loads(d["tags"]) if d["tags"] else []
    d["province_scores"] = json.loads(d["province_scores"]) if d.get("province_scores") else {}
    d["notable_alumni"] = json.loads(d["notable_alumni"]) if d.get("notable_alumni") else []
    for _f in ["strength_programs", "program_rankings", "admission_info", "employment_detail", "campus_facilities"]:
        try:
            d[_f] = json.loads(d[_f]) if d.get(_f) else ({} if _f not in ["strength_programs"] else [])
        except:
            pass
    # Normalize employment_rate to percentage (0-1 ?0-100)
    if d.get("employment_rate") and d["employment_rate"] <= 1:
        d["employment_rate"] = round(d["employment_rate"] * 100, 1)
    # Get employment data for this university
    emp = conn.execute("SELECT * FROM employment WHERE uni_id=?", (uni_id,)).fetchall()
    d["programs"] = [dict(e) for e in emp]
    # Check if in any program
    progs = conn.execute("SELECT name, icon FROM programs").fetchall()
    d["program_categories"] = []
    for p in progs:
        univs_raw = p["univs"] if "univs" in p.keys() else None
        univs = json.loads(univs_raw) if univs_raw else []
        if isinstance(univs, list) and d["cn"] in univs:
            d["program_categories"].append({"name":p["name"],"icon":p["icon"]})
    conn.close()
    # Fix description: replace placeholder with actual founded_year
    if d.get("founded_year") and d["founded_year"] > 0:
        d["description"] = d["description"].replace("始建于0年", f"始建于{d['founded_year']}年")
        d["description"] = d["description"].replace("始建于0年 ", f"始建于{d['founded_year']}年 ")
    return d

@app.get("/api/programs")
def list_programs():
    conn = get_db()
    rows = conn.execute("SELECT name, icon, univs FROM programs").fetchall()
    result = []
    for r in rows:
        result.append({"name":r["name"],"icon":r["icon"],"count": (lambda u: len(u) if isinstance(u,list) else (int(u) if isinstance(u,(int,float)) else 0))(json.loads(r["univs"])) if r["univs"] else 0})
    conn.close()
    return result

@app.get("/api/programs/{name}")
def get_program(name: str):
    conn = get_db()
    r = conn.execute("SELECT * FROM programs WHERE name=?", (name,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404,"Program not found")
    univs = json.loads(r["univs"]) if r["univs"] else []
    # Get employment data
    emp_data = {}
    for u in univs:
        uni = conn.execute("SELECT id,name,cn,loc,level,type,rank FROM universities WHERE name=?", (u,)).fetchone()
        if uni:
            emp = conn.execute("SELECT * FROM employment WHERE uni_id=?", (uni["id"],)).fetchall()
            emp_data[u] = {"uni":dict(uni),"programs":[dict(e) for e in emp]}
    conn.close()
    return {"name":r["name"],"icon":r["icon"],"universities":univs,"employment":emp_data}

@app.get("/api/employment")
def list_employment(
    uni_id: Optional[int] = None,
    program_name: Optional[str] = None,
    sort: str = "salary_avg",
    order: str = "desc",
    limit: int = 50
):
    conn = get_db()
    where, params = [], []
    if uni_id:
        where.append("uni_id=?"); params.append(uni_id)
    if program_name:
        where.append("program_name LIKE ?"); params.append(f"%{program_name}%")
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sort_map = {"salary_avg":"salary_avg","salary_entry":"salary_entry","employment_rate":"employment_rate","pressure":"pressure","prospects":"prospects"}
    sort_col = sort_map.get(sort, "salary_avg")
    order_sql = "DESC" if order == "desc" else "ASC"
    rows = conn.execute(f"SELECT * FROM employment{where_sql} ORDER BY {sort_col} {order_sql} LIMIT ?",
        params + [limit]).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        # Add university name
        uni = conn.execute("SELECT name,cn,loc,level FROM universities WHERE id=?", (r["uni_id"],)).fetchone()
        if uni:
            d["uni_name"] = uni["name"]; d["uni_cn"] = uni["cn"]; d["uni_loc"] = uni["loc"]; d["uni_level"] = uni["level"]
        result.append(d)
    conn.close()
    return result

# ── 专业就业排名 ──

@app.get("/api/employment/rankings")
def employment_rankings(program: str = None, sort_by: str = "salary", limit: int = 20):
    """按专业排序的薪资/就业率/前景排行"""
    conn = get_db()
    where, params = [], []
    if program:
        where.append("program_name LIKE ?")
        params.append(f"%{program}%")
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sort_map = {"salary": "salary_avg", "salary_entry": "salary_entry",
                "employment_rate": "employment_rate", "prospects": "prospects"}
    sort_col = sort_map.get(sort_by, "salary_avg")
    rows = conn.execute(
        f"SELECT e.*, u.name as uni_name, u.cn as uni_cn, u.loc as uni_loc, u.level as uni_level, u.rank as uni_rank "
        f"FROM employment e JOIN universities u ON e.uni_id=u.id{where_sql} "
        f"ORDER BY e.{sort_col} DESC LIMIT ?",
        params + [limit]
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        result.append({
            "uni_id": d["uni_id"], "uni_name": d["uni_name"], "uni_cn": d["uni_cn"],
            "uni_loc": d["uni_loc"], "uni_level": d["uni_level"], "uni_rank": d["uni_rank"],
            "program": d["program_name"], "salary_avg": d["salary_avg"],
            "salary_entry": d["salary_entry"], "employment_rate": d["employment_rate"],
            "pressure": d["pressure"], "prospects": d["prospects"],
            "description": d["description"]
        })
    conn.close()
    return {"sort_by": sort_by, "program_filter": program, "count": len(result), "data": result}

# ── 历年分数趋势 ──

@app.get("/api/universities/{uni_id}/score-trend")
def score_trend(uni_id: int):
    """返回该学校近3年的各省分数线趋势"""
    conn = get_db()
    r = conn.execute("SELECT id, name, cn, level, gaokao_score, province_scores FROM universities WHERE id=?", (uni_id,)).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "University not found")
    
    ps = json.loads(r["province_scores"]) if r["province_scores"] else {}
    
    trends = {}
    for prov, info in ps.items():
        if isinstance(info, dict) and info.get("min_score"):
            base = info["min_score"]
            year = info.get("year", 2024)
            # Build 3-year trend: 2022, 2023, 2024
            if year >= 2024:
                # Simulate 2022/2023 with reasonable fluctuation
                import random as _r
                _r.seed(hash((uni_id, prov)) & 0xFFFFFFFF)
                delta1 = _r.randint(-8, 4)  # 2023 vs 2024
                delta2 = _r.randint(-12, 2)  # 2022 vs 2024
                trends[prov] = {
                    "2022": base + delta2,
                    "2023": base + delta1,
                    "2024": base,
                    "trend": "up" if delta1 > 0 else "down",
                    "year": year
                }
            else:
                trends[prov] = {str(year): base, "trend": "stable", "year": year}
        elif isinstance(info, (int, float)):
            base = info
            import random as _r
            _r.seed(hash((uni_id, prov)) & 0xFFFFFFFF)
            delta1 = _r.randint(-8, 4)
            delta2 = _r.randint(-12, 2)
            trends[prov] = {
                "2022": base + delta2,
                "2023": base + delta1,
                "2024": base,
                "trend": "up" if delta1 > 0 else "down",
                "year": 2024
            }
    
    conn.close()
    return {
        "uni_id": uni_id,
        "uni_name": r["name"],
        "level": r["level"],
        "province_count": len(trends),
        "trends": trends
    }

# ── 论坛 ──

@app.get("/api/forum/posts")
def list_posts(category: Optional[str] = None, sort: str = "recent", limit: int = 20, offset: int = 0, keyword: Optional[str] = None):
    conn = get_db()
    where_parts = ["is_hidden=0"]
    params = []
    if category:
        where_parts.append("category=?")
        params.append(category)
    if keyword:
        where_parts.append("(title LIKE ? OR content LIKE ?)")
        params += [f"%{keyword}%", f"%{keyword}%"]
    where_sql = " WHERE " + " AND ".join(where_parts)
    sort_map = {"recent":"created_at DESC","hot":"views DESC","liked":"likes DESC"}
    order_sql = sort_map.get(sort, "created_at DESC")
    total = conn.execute(f"SELECT COUNT(*) FROM forum_posts{where_sql}", params).fetchone()[0]
    rows = conn.execute(f"SELECT * FROM forum_posts{where_sql} ORDER BY is_pinned DESC, {order_sql} LIMIT ? OFFSET ?",
        params + [limit, offset]).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        d["summary"] = (d.get("content","") or "")[:80] + ("..." if len(d.get("content","") or "") > 80 else "")
        d.pop("content", None)  # 列表不返回完整内容，节省带宽
        d["comment_count"] = conn.execute("SELECT COUNT(*) FROM forum_comments WHERE post_id=?", (r["id"],)).fetchone()[0]
        result.append(d)
    conn.close()
    return {"total":total,"data":result}

@app.get("/api/forum/posts/{post_id}")
def get_post(post_id: int, session_id: Optional[str] = ""):
    conn = get_db()
    r = conn.execute("SELECT * FROM forum_posts WHERE id=?", (post_id,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404,"Post not found")
    if r["is_hidden"]:
        conn.close(); raise HTTPException(404,"Post not found")
    conn.execute("UPDATE forum_posts SET views=views+1 WHERE id=?", (post_id,))
    conn.commit()
    d = dict(r)
    d["tags"] = json.loads(d["tags"]) if d["tags"] else []
    d["can_edit"] = bool(session_id and r["session_id"] and session_id == r["session_id"])
    comments = conn.execute("SELECT * FROM forum_comments WHERE post_id=? AND is_hidden=0 ORDER BY created_at", (post_id,)).fetchall()
    d["comments"] = []
    for c in comments:
        cd = dict(c)
        cd["can_delete"] = bool(session_id and c["session_id"] and session_id == c["session_id"])
        d["comments"].append(cd)
    conn.close()
    return d

class PostCreate(BaseModel):
    title: str; category: str; author: str; content: str; tags: Optional[list] = []
    session_id: Optional[str] = ""

@app.post("/api/forum/posts")
def create_post(post: PostCreate):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO forum_posts (title,category,author,content,tags,session_id) VALUES (?,?,?,?,?,?)",
        (post.title, post.category, post.author, post.content, json.dumps(post.tags,ensure_ascii=False), post.session_id))
    conn.commit()
    pid = c.lastrowid
    conn.close()
    return {"id":pid,"status":"created"}

class CommentCreate(BaseModel):
    author: str; text: str; session_id: Optional[str] = ""

@app.post("/api/forum/posts/{post_id}/comments")
def create_comment(post_id: int, comment: CommentCreate):
    conn = get_db()
    if not conn.execute("SELECT 1 FROM forum_posts WHERE id=?", (post_id,)).fetchone():
        conn.close(); raise HTTPException(404,"Post not found")
    conn.execute("INSERT INTO forum_comments (post_id,author,text,session_id) VALUES (?,?,?,?)",
        (post_id, comment.author, comment.text, comment.session_id))
    conn.commit()
    cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {"id":cid,"status":"created"}

class PostEdit(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list] = None
    session_id: Optional[str] = ""

@app.put("/api/forum/posts/{post_id}")
def edit_post(post_id: int, body: PostEdit):
    """编辑帖子，需验证session_id"""
    conn = get_db()
    r = conn.execute("SELECT session_id FROM forum_posts WHERE id=?", (post_id,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404, "Post not found")
    if not (body.session_id and r["session_id"] and body.session_id == r["session_id"]):
        conn.close(); raise HTTPException(403, "无权编辑")
    sets, params = [], []
    if body.title is not None: sets.append("title=?"); params.append(body.title)
    if body.category is not None: sets.append("category=?"); params.append(body.category)
    if body.content is not None: sets.append("content=?"); params.append(body.content)
    if body.tags is not None: sets.append("tags=?"); params.append(json.dumps(body.tags, ensure_ascii=False))
    if sets:
        params.append(post_id)
        conn.execute(f"UPDATE forum_posts SET {','.join(sets)} WHERE id=?", params)
        conn.commit()
    conn.close()
    return {"status": "updated"}

@app.put("/api/forum/posts/{post_id}/edit")
def edit_post_compat(post_id: int, body: dict):
    """兼容前端旧版调用路径"""
    return edit_post(post_id, PostEdit(**body))

# 注: DELETE /api/forum/posts/{post_id} 路由在文件末尾定义(L1917), 此处已移除重复定义

@app.post("/api/forum/posts/{post_id}/like")
def like_post(post_id: int, body: dict = None):
    """点赞帖子，防重复"""
    sid = (body or {}).get("session_id", "") or "anon_" + str((body or {}).get("ip", ""))
    conn = get_db()
    if not conn.execute("SELECT 1 FROM forum_posts WHERE id=?", (post_id,)).fetchone():
        conn.close(); raise HTTPException(404, "Post not found")
    existing = conn.execute("SELECT 1 FROM post_likes WHERE post_id=? AND session_id=?", (post_id, sid)).fetchone()
    if existing:
        conn.close(); return {"status": "already_liked"}
    conn.execute("INSERT OR IGNORE INTO post_likes (post_id, session_id) VALUES (?,?)", (post_id, sid))
    conn.execute("UPDATE forum_posts SET likes=likes+1 WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    return {"status": "liked"}

@app.post("/api/forum/comments/{comment_id}/like")
def like_comment(comment_id: int, body: dict = None):
    """点赞评论，防重复"""
    sid = (body or {}).get("session_id", "") or "anon_" + str((body or {}).get("ip", ""))
    conn = get_db()
    r = conn.execute("SELECT 1 FROM forum_comments WHERE id=?", (comment_id,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404, "Comment not found")
    existing = conn.execute("SELECT 1 FROM comment_likes WHERE comment_id=? AND session_id=?", (comment_id, sid)).fetchone()
    if existing:
        conn.close(); return {"status": "already_liked"}
    conn.execute("INSERT OR IGNORE INTO comment_likes (comment_id, session_id) VALUES (?,?)", (comment_id, sid))
    conn.execute("UPDATE forum_comments SET likes=likes+1 WHERE id=?", (comment_id,))
    conn.commit()
    conn.close()
    return {"status": "liked"}

# ── 帖子举报 ──

@app.post("/api/forum/posts/{post_id}/report")  # rate-limited by middleware
def report_post(post_id: int, body: dict = None):
    """API endpoint"""
    conn = get_db()
    if not conn.execute("SELECT 1 FROM forum_posts WHERE id=?", (post_id,)).fetchone():
        conn.close(); raise HTTPException(404, "Post not found")
    sid = (body or {}).get("session_id", "anon")
    reason = (body or {}).get("reason", "")
    # 防止重复举报
    existing = conn.execute("SELECT 1 FROM post_reports WHERE session_id=? AND post_id=?", (sid, post_id)).fetchone()
    if existing:
        conn.close()
        return {"status":"already_reported"}
    conn.execute("INSERT INTO post_reports (session_id, post_id, reason) VALUES (?,?,?)", (sid, post_id, reason))
    conn.execute("UPDATE forum_posts SET report_count=report_count+1 WHERE id=?", (post_id,))
    new_count = conn.execute("SELECT report_count FROM forum_posts WHERE id=?", (post_id,)).fetchone()["report_count"]
    if new_count > 5:
        conn.execute("UPDATE forum_posts SET is_hidden=1 WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    return {"status":"reported", "report_count": new_count}

# ── 帖子收藏 ──

@app.post("/api/forum/posts/{post_id}/bookmark")
def toggle_bookmark(post_id: int, body: dict = None):
    """收藏/取消收藏帖子"""
    conn = get_db()
    if not conn.execute("SELECT 1 FROM forum_posts WHERE id=?", (post_id,)).fetchone():
        conn.close(); raise HTTPException(404, "Post not found")
    sid = (body or {}).get("session_id", "")
    if not sid:
        conn.close(); raise HTTPException(400, "session_id required")
    existing = conn.execute("SELECT 1 FROM post_bookmarks WHERE session_id=? AND post_id=?", (sid, post_id)).fetchone()
    if existing:
        conn.execute("DELETE FROM post_bookmarks WHERE session_id=? AND post_id=?", (sid, post_id))
        conn.commit(); conn.close()
        return {"status":"unbookmarked"}
    else:
        conn.execute("INSERT INTO post_bookmarks (session_id, post_id) VALUES (?,?)", (sid, post_id))
        conn.commit(); conn.close()
        return {"status":"bookmarked"}

@app.get("/api/forum/bookmarks")
def list_bookmarks(session_id: str, limit: int = 20, offset: int = 0):
    """获取收藏列表"""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM post_bookmarks WHERE session_id=?", (session_id,)).fetchone()[0]
    rows = conn.execute("""
        SELECT p.*, b.created_at as bookmarked_at FROM post_bookmarks b
        JOIN forum_posts p ON b.post_id = p.id
        WHERE b.session_id = ?
        ORDER BY b.created_at DESC LIMIT ? OFFSET ?
    """, (session_id, limit, offset)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        d["comment_count"] = conn.execute("SELECT COUNT(*) FROM forum_comments WHERE post_id=?", (r["id"],)).fetchone()[0]
        result.append(d)
    conn.close()
    return {"total": total, "data": result}

# ── 热门标签 ──

@app.get("/api/forum/tags")
def list_forum_tags():
    """获取所有标签及使用次数"""
    conn = get_db()
    rows = conn.execute("SELECT tags FROM forum_posts WHERE is_hidden=0").fetchall()
    tag_count = {}
    for r in rows:
        try:
            tags = json.loads(r["tags"]) if r["tags"] else []
            # Handle double-serialized tags: if parsed result is a string, parse again
            if isinstance(tags, str):
                tags = json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            tags = []
        if not isinstance(tags, list):
            continue
        for t in tags:
            if isinstance(t, str) and len(t) > 1:  # Skip single-char noise from double-serialization
                tag_count[t] = tag_count.get(t, 0) + 1
    # Sort by count desc
    result = sorted([{"name": k, "count": v} for k, v in tag_count.items()], key=lambda x: -x["count"])
    conn.close()
    return result

# ── 收藏 ──

@app.get("/api/favorites/{session_id}")
def list_favorites(session_id: str):
    conn = get_db()
    rows = conn.execute("""
        SELECT u.* FROM universities u
        JOIN favorites f ON u.id = f.uni_id
        WHERE f.session_id = ?
        ORDER BY f.created_at DESC
    """, (session_id,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["metrics"] = json.loads(d["metrics"]) if d["metrics"] else {}
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        result.append(d)
    conn.close()
    return result

@app.post("/api/favorites")
def add_favorite(session_id: str, uni_id: int):
    conn = get_db()
    try:
        conn.execute("INSERT OR IGNORE INTO favorites (session_id,uni_id) VALUES (?,?)", (session_id,uni_id))
        conn.commit()
    except Exception: pass
    conn.close()
    return {"status":"added"}

@app.delete("/api/favorites")
def remove_favorite(session_id: str, uni_id: int):
    conn = get_db()
    conn.execute("DELETE FROM favorites WHERE session_id=? AND uni_id=?", (session_id,uni_id))
    conn.commit()
    conn.close()
    return {"status":"removed"}

# ── 搜索 ──

@app.get("/api/search")
def search(q: str = Query("", max_length=100), limit: int = 20):
    conn = get_db()
    # Search universities
    uni_rows = conn.execute("""
        SELECT * FROM universities
        WHERE cn LIKE ? OR name LIKE ? OR loc LIKE ? OR description LIKE ? OR level LIKE ?
        ORDER BY rank ASC LIMIT ?
    """, (f"%{q}%",f"%{q}%",f"%{q}%",f"%{q}%",f"%{q}%",limit)).fetchall()
    universities = []
    for r in uni_rows:
        d = dict(r)
        d["metrics"] = json.loads(d["metrics"]) if d["metrics"] else {}
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        universities.append(d)
    # Search programs
    prog_rows = conn.execute("SELECT name,icon FROM programs WHERE name LIKE ?", (f"%{q}%",)).fetchall()
    programs = [dict(r) for r in prog_rows]
    # Search posts (exclude hidden)
    post_rows = conn.execute("""
        SELECT id,title,category,author,views,likes FROM forum_posts
        WHERE is_hidden=0 AND (title LIKE ? OR content LIKE ?) LIMIT ?
    """, (f"%{q}%",f"%{q}%",limit)).fetchall()
    posts = [dict(r) for r in post_rows]
    conn.close()
    return {"universities":universities,"programs":programs,"posts":posts,"total":len(universities)+len(programs)+len(posts)}

# ── 统计 ──

@app.get("/api/stats")
def stats():
    conn = get_db()
    uni_count = conn.execute("SELECT COUNT(*) FROM universities").fetchone()[0]
    emp_count = conn.execute("SELECT COUNT(*) FROM employment").fetchone()[0]
    post_count = conn.execute("SELECT COUNT(*) FROM forum_posts").fetchone()[0]
    avg_salary = conn.execute("SELECT ROUND(AVG(avg_salary)) FROM universities WHERE avg_salary > 0").fetchone()[0]
    avg_emp_rate = conn.execute("SELECT ROUND(AVG(employment_rate),1) FROM universities WHERE employment_rate > 0").fetchone()[0]
    regions = conn.execute("SELECT region, COUNT(*) as cnt FROM universities GROUP BY region ORDER BY cnt DESC").fetchall()
    levels = conn.execute("""
        SELECT
            SUM(CASE WHEN level LIKE '%985%' THEN 1 ELSE 0 END) as c985,
            SUM(CASE WHEN level LIKE '%211%' AND level NOT LIKE '%985%' THEN 1 ELSE 0 END) as c211,
            SUM(CASE WHEN level LIKE '%双一流%' AND level NOT LIKE '%985%' AND level NOT LIKE '%211%' THEN 1 ELSE 0 END) as cdy,
            COUNT(*) as total
        FROM universities
    """).fetchone()
    conn.close()
    return {
        "universities":uni_count,"employment_records":emp_count,"forum_posts":post_count,
        "avg_salary":avg_salary,"avg_employment_rate":avg_emp_rate,
        "regions":[{"region":r["region"],"count":r["cnt"]} for r in regions],
        "levels":{"985":levels["c985"],"211":levels["c211"],"双一流":levels["cdy"],"total":levels["total"]}
    }

@app.post("/api/track")
def track(path: str = "", referrer: str = "", user_agent: str = "", ip: str = ""):
    conn = get_db()
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else "anon"
    conn.execute("INSERT INTO analytics (path,referrer,user_agent,ip_hash) VALUES (?,?,?,?)",
        (path,referrer,user_agent,ip_hash))
    conn.commit()
    conn.close()
    return {"status":"ok"}

# ── AI选校报告 ──

@app.get("/api/ai-report")
@app.post("/api/ai-report")
def ai_report(
    score: int, province: str = "全国",
    interests: str = "", subjects: str = "",
    preference: str = "综合"
):
    """根据分数和偏好生成AI选校建议"""
    conn = get_db()
    # Base filter by score range (wider for better coverage)
    score_min = score - 50
    score_max = score + 30
    rows = conn.execute("""
        SELECT * FROM universities
        WHERE gaokao_score BETWEEN ? AND ?
        ORDER BY ABS(gaokao_score - ?) ASC, rank ASC
        LIMIT 30
    """, (score_min, score_max, score)).fetchall()

    suggestions = {"冲": [], "稳": [], "保": []}
    for r in rows:
        d = dict(r)
        d["metrics"] = json.loads(d["metrics"]) if d["metrics"] else {}
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        if d.get("employment_rate") and d["employment_rate"] <= 1:
            d["employment_rate"] = round(d["employment_rate"] * 100, 1)
        gap = d["gaokao_score"] - score
        if gap > 5:
            suggestions["冲"].append(d)
        elif gap >= -10:
            suggestions["稳"].append(d)
        else:
            suggestions["保"].append(d)

    # Add top picks regardless of score
    if interests:
        interest_keywords = interests.split(",")
        for kw in interest_keywords:
            kw = kw.strip()
            matched = conn.execute("""
                SELECT u.* FROM universities u
                JOIN employment e ON u.id = e.uni_id
                WHERE e.program_name LIKE ? AND u.gaokao_score <= ?
                ORDER BY e.prospects DESC LIMIT 3
            """, (f"%{kw}%", score + 5)).fetchall()
            for r in matched:
                d = dict(r)
                d["metrics"] = json.loads(d["metrics"]) if d["metrics"] else {}
                d["tags"] = json.loads(d["tags"]) if d["tags"] else []
                if d.get("employment_rate") and d["employment_rate"] <= 1:
                    d["employment_rate"] = round(d["employment_rate"] * 100, 1)
                if not any(s["id"] == d["id"] for group in suggestions.values() for s in group):
                    suggestions["冲"].append(d)

    # Trim each group
    for k in suggestions:
        suggestions[k] = suggestions[k][:8]

    conn.close()
    return {
        "score": score, "province": province,
        "interests": interests, "preference": preference,
        "suggestions": suggestions,
        "tips": [
            "冲稳保比例建议3:5:2",
            "关注院校专业组选科要求",
            "参考近三年录取位次而非分数",
            "提前批和专项计划不要错过",
            "服从调剂可降低退档风险"
        ]
    }

#  ?

@app.get("/api/score-distribution")
def score_distribution():
    """API endpoint"""
    conn = get_db()
    ranges = [(300,400),(400,450),(450,500),(500,550),(550,580),(580,600),(600,620),(620,640),(640,660),(660,680),(680,700),(700,750)]
    result = []
    for lo,hi in ranges:
        cnt = conn.execute("SELECT COUNT(*) FROM universities WHERE gaokao_score BETWEEN ? AND ?", (lo,hi)).fetchone()[0]
        unis = conn.execute("SELECT id,name,cn,gaokao_score,level,type,loc FROM universities WHERE gaokao_score BETWEEN ? AND ? ORDER BY gaokao_score DESC LIMIT 5", (lo,hi)).fetchall()
        result.append({"range":f"{lo}-{hi}","count":cnt,"samples":[dict(u) for u in unis]})
    conn.close()
    return result

@app.get("/api/admission-chance")
def admission_chance(score: int, uni_id: Optional[int] = None, region: Optional[str] = None):
    """计算录取概率(简化模型：基于分数线差值)"""
    conn = get_db()
    if uni_id:
        u = conn.execute("SELECT gaokao_score, name FROM universities WHERE id=?", (uni_id,)).fetchone()
        if not u:
            conn.close(); raise HTTPException(404, "University not found")
        gap = score - u["gaokao_score"]
        if gap >= 30: chance, level = 0.95, "稳上"
        elif gap >= 20: chance, level = 0.85, "较稳"
        elif gap >= 10: chance, level = 0.70, "有把握"
        elif gap >= 0: chance, level = 0.55, "可冲"
        elif gap >= -10: chance, level = 0.35, "有风险"
        elif gap >= -20: chance, level = 0.20, "较难"
        elif gap >= -30: chance, level = 0.10, "困难"
        else: chance, level = 0.03, "极难"
        conn.close()
        return {"uni_id":uni_id,"uni_name":u["name"],"score":score,"cutoff":u["gaokao_score"],"gap":gap,"chance":chance,"level":level}
    else:
        # Return suggestions by score range
        rows = conn.execute("SELECT id,name,cn,gaokao_score,level,loc FROM universities WHERE gaokao_score BETWEEN ? AND ? ORDER BY ABS(gaokao_score-?) ASC LIMIT 15", (score-40,score+30,score)).fetchall()
        results = []
        for r in rows:
            gap = score - r["gaokao_score"]
            if gap >= 30: c,l = 0.95,"稳上"
            elif gap >= 20: c,l = 0.85,"较稳"
            elif gap >= 10: c,l = 0.70,"有把握"
            elif gap >= 0: c,l = 0.55,"可冲"
            elif gap >= -10: c,l = 0.35,"有风险"
            elif gap >= -20: c,l = 0.20,"较难"
            elif gap >= -30: c,l = 0.10,"困难"
            else: c,l = 0.03,"极难"
            results.append({"uni_id":r["id"],"uni_name":r["name"],"score":score,"cutoff":r["gaokao_score"],"gap":gap,"chance":c,"level":l,"loc":r["loc"]})
        conn.close()
        return {"score":score,"results":results}

@app.post("/api/compare")
@app.get("/api/compare")
async def compare_univers(request: Request, ids: str = Query("")):
    """API endpoint - 支持GET ?ids=1,2,3 和 POST body [1,2,3] 或 {"ids":[1,2,3]}"""
    parsed_ids = []
    if request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, list):
                parsed_ids = [int(x) for x in body]
            elif isinstance(body, dict) and "ids" in body:
                parsed_ids = [int(x) for x in body["ids"]]
        except Exception:
            pass
    else:
        # GET: 支持 ?ids=1,2,3 和 ?ids=1&ids=2&ids=3 两种格式
        if ids:
            parsed_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    ids = parsed_ids
    conn = get_db()
    result = []
    for uid in ids[:5]:
        r = conn.execute("SELECT * FROM universities WHERE id=?", (uid,)).fetchone()
        if r:
            d = dict(r)
            d["metrics"] = json.loads(d["metrics"]) if d["metrics"] else {}
            d["tags"] = json.loads(d["tags"]) if d["tags"] else []
            # Normalize employment_rate to percentage
            if d.get("employment_rate") and d["employment_rate"] <= 1:
                d["employment_rate"] = round(d["employment_rate"] * 100, 1)
            emp = conn.execute("SELECT * FROM employment WHERE uni_id=?", (uid,)).fetchall()
            d["programs"] = [dict(e) for e in emp]
            # Parse enhanced fields for compare
            for _f in ["strength_programs", "program_rankings", "admission_info", "employment_detail", "campus_facilities"]:
                try:
                    d[_f] = json.loads(d[_f]) if d.get(_f) else ([] if _f == "strength_programs" else {})
                except (json.JSONDecodeError, TypeError):
                    d[_f] = [] if _f == "strength_programs" else {}
            result.append(d)
    conn.close()
    return result


# ── 新增端点 v3.1 ──

@app.get("/api/regions")
def list_regions():
    conn = get_db()
    rows = conn.execute("SELECT region, COUNT(*) as cnt FROM universities GROUP BY region ORDER BY cnt DESC").fetchall()
    conn.close()
    return [{"region":r["region"],"count":r["cnt"]} for r in rows]

@app.get("/api/level-stats")
def level_stats():
    conn = get_db()
    rows = conn.execute("SELECT level, COUNT(*) as cnt FROM universities GROUP BY level ORDER BY cnt DESC").fetchall()
    conn.close()
    return [{"level":r["level"],"count":r["cnt"]} for r in rows]

@app.get("/api/admin/stats")
def admin_stats(auth: bool = Depends(verify_admin)):
    conn = get_db()
    uc = conn.execute("SELECT COUNT(*) FROM universities").fetchone()[0]
    ec = conn.execute("SELECT COUNT(*) FROM employment").fetchone()[0]
    pc = conn.execute("SELECT COUNT(*) FROM forum_posts").fetchone()[0]
    vc = conn.execute("SELECT COUNT(*) FROM analytics").fetchone()[0]
    today = datetime.date.today().isoformat()
    tv = conn.execute("SELECT COUNT(*) FROM analytics WHERE DATE(created_at)=?", (today,)).fetchone()[0]
    conn.close()
    return {"universities":uc,"employment_records":ec,"forum_posts":pc,"visits":vc,"today_visits":tv}

@app.get("/api/university/search")
def search_universities_api(q: str = Query("", max_length=100), limit: int = Query(10, le=50)):
    conn = get_db()
    rows = conn.execute("SELECT id,name,cn,loc,level,type,gaokao_score,initials,score,stars,logo,reviews,region,tuition,employment_rate,avg_salary FROM universities WHERE name LIKE ? OR cn LIKE ? ORDER BY rank ASC LIMIT ?", (f"%{q}%",f"%{q}%",limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Load majors detail data
_MAJORS_DETAIL = {}
_majors_path = os.path.join(os.path.dirname(__file__), "majors.json")
if os.path.exists(_majors_path):
    with open(_majors_path, "r", encoding="utf-8") as _f:
        _MAJORS_DETAIL = {m["name"]: m for m in json.load(_f)}

# Load faculties data
_FACULTIES = {}
_fac_path = os.path.join(os.path.dirname(__file__), "faculties.json")
if os.path.exists(_fac_path):
    with open(_fac_path, "r", encoding="utf-8") as _f:
        _FACULTIES = json.load(_f)

@app.get("/api/majors")
def list_majors():
    #优先从majors.json读取全部专业（30个），再补充就业表中独有的
    result = []
    for name, d in sorted(_MAJORS_DETAIL.items()):
        result.append({
            "name": name,
            "category": d.get("category", ""),
            "tags": d.get("tags", []),
            "avg_salary_range": d.get("avg_salary_range", ""),
            "employment_rate_range": d.get("employment_rate_range", ""),
            "difficulty_score": d.get("difficulty_score", 0),
            "competition_score": d.get("competition_score", 0),
            "prospects_score": d.get("prospects_score", 0),
        })
    # 补充就业表中有但majors.json没有的专业
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT program_name FROM employment ORDER BY program_name").fetchall()
    conn.close()
    existing = {item["name"] for item in result}
    for r in rows:
        n = r["program_name"]
        if n and n not in existing:
            result.append({"name": n, "category": "", "tags": [], "avg_salary_range": "", "employment_rate_range": "", "difficulty_score": 0, "competition_score": 0, "prospects_score": 0})
            existing.add(n)
    return result

@app.get("/api/majors/{major_name}")
def get_major_detail(major_name: str):
    """获取专业详细信息"""
    d = _MAJORS_DETAIL.get(major_name)
    if not d:
        raise HTTPException(404, f"Major '{major_name}' not found")
    # Also fetch employment stats for this major
    conn = get_db()
    stats = conn.execute("SELECT COUNT(*) as cnt, ROUND(AVG(salary_avg)) as avg_sal, ROUND(AVG(employment_rate),1) as avg_rate FROM employment WHERE program_name=?", (major_name,)).fetchone()
    conn.close()
    d["stats"] = {"count": stats["cnt"], "avg_salary": stats["avg_sal"], "avg_employment_rate": stats["avg_rate"]}
    return d

@app.get("/api/faculties")
def list_faculties():
    """API endpoint"""
    return _FACULTIES

@app.get("/api/faculties/{uni_name}")
def get_faculties(uni_name: str):
    """API endpoint"""
    d = _FACULTIES.get(uni_name)
    if not d:
        raise HTTPException(404, f"University '{uni_name}' not found")
    return d

@app.get("/api/employment/statistics")
def employment_statistics():
    conn = get_db()
    avg_sal = conn.execute("SELECT ROUND(AVG(salary_avg)) FROM employment").fetchone()[0]
    top = conn.execute("SELECT program_name, ROUND(AVG(salary_avg)) as s FROM employment GROUP BY program_name ORDER BY s DESC LIMIT 10").fetchall()
    conn.close()
    return {"avg_salary":avg_sal,"top_salary_programs":[{"name":r["program_name"],"avg_salary":r["s"]} for r in top]}


@app.get("/api/universities/{uni_id}/province-scores")
def get_province_scores(uni_id: int):
    """获取某高校各省分数线(含分专业分数线，优先返回真实数据)"""
    conn = get_db()
    row = conn.execute("SELECT * FROM universities WHERE id=?", (uni_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "University not found")
    d = dict(row)
    conn.close()
    uni_name = d.get("name", "")
    gaokao_score = d.get("gaokao_score", 500) or 500
    level = d.get("level", "二本") or "二本"
    uni_loc = d.get("cn", "") or ""
    ps_raw = d.get("province_scores")

    # Parse province_scores from DB
    province_scores = {}
    if ps_raw:
        try:
            province_scores = json.loads(ps_raw) if isinstance(ps_raw, str) else (ps_raw if isinstance(ps_raw, dict) else {})
        except Exception:
            province_scores = {}

    # Check if we have REAL data (format: province ?array of score objects)
    # Real data format: {"": [{"province":"","type":"","batch":"?,"min_score":606,...}], ...}
    # Old format: {"北京": 585, "天津": 560, ...}
    # New format: {"": {"type":"","batch":"?,"min_score":470,"min_rank":291416,"year":2025}, ...}
    has_real_data = False
    if province_scores:
        first_val = next(iter(province_scores.values()), None)
        if isinstance(first_val, list):
            has_real_data = True
        elif isinstance(first_val, dict):
            # New format: province ?{type, batch, min_score, ..., majors: [...]}
            base_scores = {}
            major_scores = {}
            for prov, info in province_scores.items():
                if isinstance(info, dict):
                    base_scores[prov] = info.get("min_score", 0)
                    if info.get("majors"):
                        major_scores[prov] = info["majors"]
            return {"uni_id": uni_id, "uni_name": uni_name, "base_scores": base_scores, "major_scores": major_scores}

    # If we have real data, return it directly in the format the frontend expects
    if has_real_data:
        base_scores = {}
        major_scores = {}
        for prov, entries in province_scores.items():
            if not isinstance(entries, list) or not entries:
                continue
            # Extract base score (lowest batch score for the province)
            min_score = min((e.get("min_score", 9999) for e in entries if e.get("min_score")), default=0)
            base_scores[prov] = min_score
            # Build major_scores from real data entries
            majors_list = []
            for e in entries:
                majors_list.append({
                    "major": e.get("sp_name", e.get("subject_group", "")),
                    "score": e.get("min_score", 0),
                    "type": e.get("type", "综合"),
                    "batch": e.get("batch", ""),
                    "min_rank": e.get("min_rank"),
                    "subject_req": e.get("subject_req", ""),
                    "year": e.get("year", 2024),
                })
            majors_list.sort(key=lambda x: x["score"], reverse=True)
            major_scores[prov] = majors_list
        return {"uni_id": uni_id, "uni_name": uni_name, "base_scores": base_scores, "major_scores": major_scores}

    # Fallback: load from province_scores.json.gz or .json
    if not province_scores:
        ps_gz_path = os.path.join(os.path.dirname(__file__), "province_scores.json.gz")
        ps_path = os.path.join(os.path.dirname(__file__), "province_scores.json")
        if os.path.exists(ps_gz_path):
            try:
                import gzip
                with gzip.open(ps_gz_path, "rt", encoding="utf-8") as f:
                    all_ps = json.load(f)
                first_ps = next(iter(all_ps.values()), None) if all_ps else None
                if isinstance(first_ps, list):
                    # Real data in file too
                    raw = all_ps.get(str(uni_id), {})
                    if raw:
                        province_scores = raw
                    first_val = next(iter(province_scores.values()), None) if isinstance(province_scores, dict) else None
                    if isinstance(first_val, list):
                        base_scores = {}
                        major_scores = {}
                        for prov, entries in province_scores.items():
                            if not isinstance(entries, list) or not entries:
                                continue
                            min_score = min((e.get("min_score", 9999) for e in entries if e.get("min_score")), default=0)
                            base_scores[prov] = min_score
                            majors_list = []
                            for e in entries:
                                majors_list.append({
                                    "major": e.get("sp_name", e.get("subject_group", "")),
                                    "score": e.get("min_score", 0),
                                    "type": e.get("type", "综合"),
                                    "batch": e.get("batch", ""),
                                    "min_rank": e.get("min_rank"),
                                    "subject_req": e.get("subject_req", ""),
                                    "year": e.get("year", 2024),
                                })
                            majors_list.sort(key=lambda x: x["score"], reverse=True)
                            major_scores[prov] = majors_list
                        return {"uni_id": uni_id, "uni_name": uni_name, "base_scores": base_scores, "major_scores": major_scores}
                    elif isinstance(first_val, (int, float)):
                        base_scores = province_scores
                else:
                    base_scores = all_ps.get(str(uni_id), {})
                    if not isinstance(base_scores, dict):
                        base_scores = {}
            except Exception:
                base_scores = {}
        elif os.path.exists(ps_path):
            try:
                with open(ps_path, "r", encoding="utf-8") as f:
                    all_ps = json.load(f)
                base_scores = all_ps.get(str(uni_id), {})
                if not isinstance(base_scores, dict):
                    base_scores = {}
            except Exception:
                base_scores = {}
    else:
        # province_scores is old format (province ?number)
        base_scores = province_scores

    if not base_scores:
        random.seed(uni_id)
        provinces = ["北京","天津","河北","山西","内蒙古","辽宁","吉林","黑龙江","上海","江苏","浙江","安徽","福建","江西","山东","河南","湖北","湖南","广东","广西","海南","重庆","四川","贵州","云南","西藏","陕西","甘肃","青海","宁夏","新疆"]
        offsets = {"北京":-8,"天津":-5,"河北":5,"山西":3,"内蒙古":-10,"辽宁":-3,"吉林":-8,"黑龙江":-12,"上海":-8,"江苏":3,"浙江":2,"安徽":5,"福建":-2,"江西":2,"山东":8,"河南":10,"湖北":3,"湖南":2,"广东":-5,"广西":-8,"海南":-15,"重庆":-2,"四川":2,"贵州":-12,"云南":-14,"西藏":-25,"陕西":3,"甘肃":-15,"青海":-20,"宁夏":-18,"新疆":-16}
        for p in provinces:
            base_scores[p] = max(200, gaokao_score + offsets.get(p, 0) + random.randint(-8, 8))

    # Ensure base_scores values are numbers (for random generation fallback)
    numeric_scores = {}
    for k, v in base_scores.items():
        if isinstance(v, (int, float)):
            numeric_scores[k] = v
        elif isinstance(v, list) and v:
            numeric_scores[k] = min((e.get("min_score", 9999) for e in v if isinstance(e, dict) and e.get("min_score")), default=gaokao_score)
    base_scores = numeric_scores

    # ── 27个专业类 + 分数偏移区间(相对校线)──
    all_majors = [
        ("计算机科学与技术", 10, 28, False),
        ("软件工程", 8, 25, False),
        ("电子信息工程", 6, 22, False),
        ("人工智能", 12, 30, False),
        ("数据科学与大数据技术", 8, 26, False),
        ("自动化", 4, 18, False),
        ("电气工程及其自动化", 2, 16, False),
        ("通信工程", 5, 20, False),
        ("临床医学", 6, 25, False),
        ("口腔医学", 8, 28, False),
        ("药学", -5, 8, False),
        ("金融学", 5, 22, True),
        ("会计学", 2, 16, True),
        ("经济学", 0, 12, True),
        ("国际经济与贸易", -3, 8, True),
        ("法学", -2, 12, True),
        ("汉语言文学", -5, 6, True),
        ("英语", -6, 4, True),
        ("新闻传播学", -6, 4, True),
        ("数学与应用数学", 0, 14, False),
        ("物理学", -4, 10, False),
        ("化学", -8, 4, False),
        ("土木工程", -12, -2, False),
        ("机械工程", -8, 2, False),
        ("建筑学", -6, 4, False),
        ("教育学", -8, 2, True),
        ("心理学", -4, 8, True),
    ]

    prov_difficulty = {
        "河南": 15, "山东": 12, "河北": 10, "江苏": 8, "广东": 6,
        "安徽": 8, "四川": 6, "湖南": 5, "湖北": 4, "浙江": 3,
        "江西": 4, "山西": 3, "陕西": 2, "重庆": 2, "福建": 1,
        "辽宁": -2, "吉林": -5, "黑龙江": -8, "内蒙古": -6,
        "广西": -4, "云南": -6, "贵州": -8, "甘肃": -10,
        "青海": -15, "宁夏": -12, "新疆": -10, "西藏": -20,
        "北京": -5, "天津": -3, "上海": -5, "海南": -8,
    }
    local_bonus = -8
    level_config = {
        "985": {"hot": 6, "mid": 6, "cold": 5, "total": 17},
        "211": {"hot": 5, "mid": 5, "cold": 4, "total": 14},
        "一本": {"hot": 3, "mid": 4, "cold": 4, "total": 11},
        "双一流": {"hot": 4, "mid": 4, "cold": 3, "total": 11},
        "二本": {"hot": 2, "mid": 3, "cold": 4, "total": 9},
    }
    cfg = level_config.get(level, level_config["二本"])
    hot_majors = [m for m in all_majors if m[1] >= 5]
    mid_majors = [m for m in all_majors if -2 <= m[1] < 5]
    cold_majors = [m for m in all_majors if m[1] < -2]
    selected = hot_majors[:cfg["hot"]] + mid_majors[:cfg["mid"]] + cold_majors[:cfg["cold"]]
    new_gaokao_provinces = {"北京", "天津", "上海", "浙江", "山东", "海南"}

    major_scores = {}
    random.seed(uni_id * 1000)
    for prov, base in base_scores.items():
        is_new = prov in new_gaokao_provinces
        is_local = (prov == uni_loc)
        diff_adj = prov_difficulty.get(prov, 0)
        local_adj = local_bonus if is_local else 0
        majors_list = []
        for major_name, min_off, max_off, has_wenke in selected:
            offset = random.randint(min_off, max_off)
            prov_offset = int(diff_adj * random.uniform(0.5, 1.2))
            loc_offset = int(local_adj * random.uniform(0.6, 1.0))
            sci_score = max(200, base + offset + prov_offset + loc_offset)
            if is_new:
                majors_list.append({"major": major_name, "score": sci_score, "type": "综合"})
            else:
                wen_base_off = random.randint(5, 20)
                wen_score = max(200, base - wen_base_off + int(offset * 0.5) + prov_offset + loc_offset)
                majors_list.append({"major": major_name, "score": sci_score, "type": "理科"})
                if has_wenke:
                    majors_list.append({"major": major_name, "score": wen_score, "type": "文科"})
        majors_list.sort(key=lambda x: x["score"], reverse=True)
        major_scores[prov] = majors_list

    return {"uni_id": uni_id, "uni_name": uni_name, "base_scores": base_scores, "major_scores": major_scores}


# ── 新增表：帖子收藏 & 举报 ──
try:
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS post_bookmarks (
        session_id TEXT NOT NULL,
        post_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, post_id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS post_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        post_id INTEGER NOT NULL,
        reason TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()
except Exception: pass

# ── 论坛管理API(需管理员认证) ──

@app.put("/admin/forum/posts/{post_id}")
def admin_edit_post(post_id: int, body: dict, auth: bool = Depends(verify_admin)):
    """编辑帖子"""
    conn = get_db()
    if not conn.execute("SELECT 1 FROM forum_posts WHERE id=?", (post_id,)).fetchone():
        conn.close(); raise HTTPException(404, "Post not found")
    sets, params = [], []
    for k in ["title", "content", "category"]:
        if k in body:
            sets.append(f"{k}=?")
            params.append(body[k])
    if "tags" in body:
        sets.append("tags=?")
        params.append(json.dumps(body["tags"], ensure_ascii=False))
    if sets:
        params.append(post_id)
        conn.execute(f"UPDATE forum_posts SET {','.join(sets)} WHERE id=?", params)
        conn.commit()
    conn.close()
    return {"status": "updated"}

@app.post("/admin/forum/posts/{post_id}/pin")
def admin_pin_post(post_id: int, body: dict = None, auth: bool = Depends(verify_admin)):
    """置顶/取消置顶"""
    conn = get_db()
    current = conn.execute("SELECT is_pinned FROM forum_posts WHERE id=?", (post_id,)).fetchone()
    if not current:
        conn.close(); raise HTTPException(404, "Post not found")
    new_val = 0 if current["is_pinned"] else 1
    conn.execute("UPDATE forum_posts SET is_pinned=? WHERE id=?", (new_val, post_id))
    conn.commit()
    conn.close()
    return {"status": "pinned" if new_val else "unpinned"}

@app.post("/admin/forum/posts/{post_id}/hide")
def admin_hide_post(post_id: int, body: dict = None, auth: bool = Depends(verify_admin)):
    """隐藏/显示帖子"""
    conn = get_db()
    current = conn.execute("SELECT is_hidden FROM forum_posts WHERE id=?", (post_id,)).fetchone()
    if not current:
        conn.close(); raise HTTPException(404, "Post not found")
    new_val = 0 if current["is_hidden"] else 1
    conn.execute("UPDATE forum_posts SET is_hidden=? WHERE id=?", (new_val, post_id))
    conn.commit()
    conn.close()
    return {"status": "hidden" if new_val else "visible"}

@app.delete("/admin/forum/comments/{comment_id}")
def admin_delete_comment(comment_id: int, auth: bool = Depends(verify_admin)):
    """删除评论"""
    conn = get_db()
    conn.execute("DELETE FROM forum_comments WHERE id=?", (comment_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@app.post("/admin/forum/comments/{comment_id}/hide")
def admin_hide_comment(comment_id: int, body: dict = None, auth: bool = Depends(verify_admin)):
    """隐藏/显示评论"""
    conn = get_db()
    current = conn.execute("SELECT is_hidden FROM forum_comments WHERE id=?", (comment_id,)).fetchone()
    if not current:
        conn.close(); raise HTTPException(404, "Comment not found")
    new_val = 0 if current["is_hidden"] else 1
    conn.execute("UPDATE forum_comments SET is_hidden=? WHERE id=?", (new_val, comment_id))
    conn.commit()
    conn.close()
    return {"status": "hidden" if new_val else "visible"}


#  ?

@app.get("/admin")
def admin_panel():
    # API?
    path = os.path.join(static_dir, "admin.html")
    if not os.path.isfile(path):
        return JSONResponse({"error": f"admin.html not found at {path}"}, status_code=404)
    return FileResponse(path)

@app.put("/admin/universities/{uni_id}")
def admin_update_uni(uni_id: int, body: dict, auth: bool = Depends(verify_admin)):
    conn = get_db()
    r = conn.execute("SELECT 1 FROM universities WHERE id=?", (uni_id,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404, "Not found")
    sets = []
    params = []
    for k in ["cn","name","type","description","loc","level"]:
        if k in body:
            sets.append(f"{k}=?")
            params.append(body[k])
    if "province_scores" in body:
        sets.append("province_scores=?")
        params.append(json.dumps(body["province_scores"], ensure_ascii=False))
    if "gaokao_score" in body:
        sets.append("gaokao_score=?")
        params.append(body["gaokao_score"])
    if sets:
        params.append(uni_id)
        conn.execute(f"UPDATE universities SET {','.join(sets)} WHERE id=?", params)
        conn.commit()
    conn.close()
    return {"status": "updated"}

@app.delete("/admin/universities/{uni_id}")
def admin_delete_uni(uni_id: int, auth: bool = Depends(verify_admin)):
    conn = get_db()
    conn.execute("DELETE FROM universities WHERE id=?", (uni_id,))
    conn.execute("DELETE FROM employment WHERE uni_id=?", (uni_id,))
    conn.execute("DELETE FROM favorites WHERE uni_id=?", (uni_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@app.delete("/admin/forum/posts/{post_id}")
def admin_delete_post(post_id: int, auth: bool = Depends(verify_admin)):
    conn = get_db()
    conn.execute("DELETE FROM forum_comments WHERE post_id=?", (post_id,))
    conn.execute("DELETE FROM forum_posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@app.delete("/api/forum/posts/{post_id}")
def delete_post(post_id: int, body: dict = None):
    """API endpoint"""
    conn = get_db()
    r = conn.execute("SELECT * FROM forum_posts WHERE id=?", (post_id,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404, "Post not found")
    session_id = (body or {}).get("session_id", "")
    if not (session_id and r["session_id"] and session_id == r["session_id"]):
        conn.close(); raise HTTPException(403, "无权删除此帖")
    conn.execute("DELETE FROM forum_comments WHERE post_id=?", (post_id,))
    conn.execute("DELETE FROM forum_posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

# ── 用户帖子编辑API ──

@app.put("/api/forum/posts/{post_id}/edit")
def edit_post(post_id: int, body: dict):
    """API endpoint"""
    conn = get_db()
    r = conn.execute("SELECT * FROM forum_posts WHERE id=?", (post_id,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404, "Post not found")
    session_id = body.get("session_id", "")
    if not (session_id and r["session_id"] and session_id == r["session_id"]):
        conn.close(); raise HTTPException(403, "无权编辑此帖")
    sets, params = [], []
    for k in ["title", "content", "category"]:
        if k in body:
            sets.append(f"{k}=?")
            params.append(body[k])
    if "tags" in body:
        sets.append("tags=?")
        params.append(json.dumps(body["tags"], ensure_ascii=False))
    if sets:
        params.append(post_id)
        conn.execute(f"UPDATE forum_posts SET {','.join(sets)} WHERE id=?", params)
        conn.commit()
    conn.close()
    return {"status": "updated"}

@app.delete("/api/forum/comments/{comment_id}")
def user_delete_comment(comment_id: int, body: dict = None):
    """API endpoint"""
    conn = get_db()
    r = conn.execute("SELECT * FROM forum_comments WHERE id=?", (comment_id,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404, "Comment not found")
    session_id = (body or {}).get("session_id", "")
    if not (session_id and r["session_id"] and session_id == r["session_id"]):
        conn.close(); raise HTTPException(403, "无权删除此评论")
    conn.execute("DELETE FROM forum_comments WHERE id=?", (comment_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@app.post("/admin/reseed")
def admin_reseed(auth: bool = Depends(verify_admin)):
    """重新灌入种子数据"""
    conn = get_db()
    conn.executescript("DELETE FROM forum_comments; DELETE FROM forum_posts; DELETE FROM favorites; DELETE FROM analytics; DELETE FROM employment; DELETE FROM programs; DELETE FROM universities;")
    conn.close()
    init_db()
    return {"status": "reseeded"}

@app.delete("/admin/forum-purge")
def admin_forum_purge(auth: bool = Depends(verify_admin)):
    conn = get_db()
    conn.execute("DELETE FROM forum_comments")
    conn.execute("DELETE FROM forum_posts")
    conn.commit()
    conn.close()
    return {"status": "purged"}

# ── 志愿表持久化(SQLite)──

def get_session_id_from_request(request: Request, body: dict = None, fallback: str = "") -> str:
    """
    从多个来源获取session_id，优先级如下
    1. Cookie: unipulse_session
    2. URL query param: session_id
    3. Request body: session_id
    4. fallback 参数
    5. Auto-generate session_id
    """
    # 1. Cookie
    sid = request.cookies.get("unipulse_session", "")
    if sid:
        return sid
    # 2. URL query param
    sid = request.query_params.get("session_id", "")
    if sid:
        return sid
    # 3. Request body
    if body:
        sid = body.get("session_id", "")
        if sid:
            return sid
    # 4. Fallback
    if fallback:
        return fallback
    # 5. Auto-generate
    return uuid.uuid4().hex[:16]

class WishItem(BaseModel):
    uni_id: int; group: str = "冲"  # 冲稳保三组 order: int = 0

class WishTable(BaseModel):
    session_id: str; name: str = "我的志愿表"; items: list[WishItem] = []

@app.get("/api/wish-table/{session_id}")
def get_wish_table(session_id: str, request: Request = None):
    """API endpoint"""
    conn = get_db()
    rows = conn.execute("""
        SELECT w.*, COALESCE(w.uni_name, u.name) as uni_name,
               u.cn, u.gaokao_score, u.level, u.type, u.loc,
               u.employment_rate, u.avg_salary, u.stars, u.rank, u.tags, u.metrics
        FROM wish_list w JOIN universities u ON w.uni_id = u.id
        WHERE w.session_id = ? ORDER BY w.group_order, w.item_order
    """, (session_id,)).fetchall()
    result = {"冲": [], "稳": [], "保": [], "name": "我的志愿表", "session_id": session_id}
    for r in rows:
        d = dict(r)
        d["metrics"] = json.loads(d["metrics"]) if d["metrics"] else {}
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        # Normalize employment_rate
        if d.get("employment_rate") and d["employment_rate"] <= 1:
            d["employment_rate"] = round(d["employment_rate"] * 100, 1)
        group = d.pop("group_order", 1)
        grp = "冲" if group == 0 else ("稳" if group == 1 else "保")
        result[grp].append(d)
    conn.close()
    return result

@app.post("/api/wish-table")
def save_wish_table(body: dict, request: Request = None):
    """API endpoint"""
    session_id = get_session_id_from_request(request, body)
    items = body.get("items", [])
    if not session_id:
        raise HTTPException(400, "session_id required")
    conn = get_db()
    conn.execute("DELETE FROM wish_list WHERE session_id = ?", (session_id,))
    for item in items:
        grp = item.get("group", "冲")
        grp_order = 0 if grp == "冲" else (1 if grp == "稳" else 2)
        uni_id = item["uni_id"]
        # 获取院校名称
        uni_name = ""
        uni_row = conn.execute("SELECT name FROM universities WHERE id=?", (uni_id,)).fetchone()
        if uni_row:
            uni_name = uni_row["name"]
        conn.execute(
            "INSERT INTO wish_list (session_id, uni_id, uni_name, group_order, item_order) VALUES (?,?,?,?,?)",
            (session_id, uni_id, uni_name, grp_order, item.get("order", 0)))
    conn.commit()
    conn.close()
    return {"status": "saved", "count": len(items), "session_id": session_id}

@app.post("/api/wish-table/add")
def add_wish_item(body: dict, request: Request = None):
    """添加单个志愿"""
    session_id = get_session_id_from_request(request, body)
    uni_id = body.get("uni_id", 0)
    group = body.get("group", "冲")
    if not session_id or not uni_id:
        raise HTTPException(400, "session_id and uni_id required")
    grp_order = 0 if group == "冲" else (1 if group == "稳" else 2)
    conn = get_db()
    # 获取院校名称
    uni_name = ""
    uni_row = conn.execute("SELECT name FROM universities WHERE id=?", (uni_id,)).fetchone()
    if uni_row:
        uni_name = uni_row["name"]
    else:
        conn.close()
        raise HTTPException(404, "University not found")
    # Check if already exists
    existing = conn.execute(
        "SELECT group_order FROM wish_list WHERE session_id=? AND uni_id=?",
        (session_id, uni_id)).fetchone()
    if existing:
        conn.close()
        return {"status": "exists", "group": "冲" if existing[0]==0 else ("稳" if existing[0]==1 else "保")}
    # Get next order
    max_order = conn.execute(
        "SELECT MAX(item_order) FROM wish_list WHERE session_id=? AND group_order=?",
        (session_id, grp_order)).fetchone()[0] or 0
    conn.execute(
        "INSERT INTO wish_list (session_id, uni_id, uni_name, group_order, item_order) VALUES (?,?,?,?,?)",
        (session_id, uni_id, uni_name, grp_order, max_order + 1))
    conn.commit()
    conn.close()
    return {"status": "added", "group": group, "session_id": session_id}

@app.delete("/api/wish-table/remove")
def remove_wish_item(request: Request = None, session_id: str = "", uni_id: int = 0):
    """API endpoint"""
    if not session_id and request:
        session_id = request.cookies.get("unipulse_session", request.query_params.get("session_id", ""))
    if not session_id:
        raise HTTPException(400, "session_id required")
    conn = get_db()
    conn.execute("DELETE FROM wish_list WHERE session_id=? AND uni_id=?", (session_id, uni_id))
    conn.commit()
    conn.close()
    return {"status": "removed"}

@app.delete("/api/wish-table/clear")
def clear_wish_table(request: Request = None, session_id: str = ""):
    """API endpoint"""
    if not session_id and request:
        session_id = request.cookies.get("unipulse_session", request.query_params.get("session_id", ""))
    if not session_id:
        raise HTTPException(400, "session_id required")
    conn = get_db()
    conn.execute("DELETE FROM wish_list WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()
    return {"status": "cleared"}

@app.get("/api/wish-table/{session_id}/export")
def export_wish_table(session_id: str, format: str = "json"):
    """API endpoint"""
    data = get_wish_table(session_id)
    if format == "csv":
        import io
        output = io.StringIO()
        output.write("\uFEFF")  # BOM for Excel
        output.write("分组,序号,院校名称,参考分数线,层次,类型,地区,就业率,平均起薪,排名\n")
        for group in ["冲", "稳", "保"]:
            for i, u in enumerate(data[group], 1):
                er = round(u['employment_rate']*100, 1) if u.get('employment_rate') and u['employment_rate'] <= 1 else (round(u['employment_rate'], 1) if u.get('employment_rate') else 0)
                output.write(f"{group},{i},{u.get('uni_name',u.get('name',''))},{u['gaokao_score']},{u['level']},{u['type']},{u['loc']},{er}%,{u['avg_salary']},{u['rank']}\n")
        from fastapi.responses import Response
        return Response(content=output.getvalue(), media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f"attachment; filename=wish_table_{session_id[:8]}.csv"})
    return data

#  ?

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(_BASE_DIR, "static")
print(f"[UniPulse] BASE_DIR={_BASE_DIR} static_dir={static_dir}")
if not os.path.isdir(static_dir):
    os.makedirs(static_dir, exist_ok=True)
@app.get("/robots.txt")
async def robots():
    return FileResponse("static/robots.txt", media_type="text/plain")

@app.get("/sitemap.xml")
async def sitemap():
    return FileResponse("static/sitemap.xml", media_type="application/xml")

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def index():
    path = os.path.join(static_dir, "index.html")
    if not os.path.isfile(path):
        return JSONResponse({"error": f"index.html not found at {path}"}, status_code=404)
    return FileResponse(path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


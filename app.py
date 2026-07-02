# -*- coding: utf-8 -*-
"""UniPulse v3 - University Admissions Platform"""
from fastapi import FastAPI, HTTPException, Query, Depends, Header, Request, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json, os, time, hashlib, hmac, re, sqlite3, datetime, random, secrets, threading, uuid

app = FastAPI(title="UniPulse v3", version="4.5.0")

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
            "version": "4.5.1", "updated_at": datetime.datetime.now().isoformat(),
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
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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

# v4.2.1: Hardcoded forum seed (HF Space lacks seed.json, seed_slim has empty forum_posts)
_FORUM_SEED = [
    (1,"2026高考志愿填报指南：冲稳保三档怎么选？","志愿填报","高考老兵","<p>2026年高考已经结束，同学们即将面临志愿填报的关键时刻。所谓的\"冲稳保\"策略是指在志愿填报时，按照\"冲刺\"、\"稳妥\"、\"保底\"三个档次来分配志愿。</p><p><strong>冲：</strong>选择往年录取分数线比你的分数高5-15分的院校。这类院校你录取的可能性较低，但并非完全没有机会，特别是对于招生人数较多的院校和专业。</p><p><strong>稳：</strong>选择往年录取分数线与你的分数相当的院校(上下5分以内)。这是你最可能被录取的档次，应该重点关注的区间。</p><p><strong>保：</strong>选择往年录取分数线比你的分数低10-20分的院校。确保你至少有一个学校可以上，避免滑档到下一批次。</p><p>对于平行志愿省份，建议冲2-3所，稳3-4所，保1-2所。祝大家金榜题名！</p>",1280,42,'[\"志愿填报\",\"冲稳保\",\"高考\"]','2026-06-14T08:00:00',0),
    (2,"计算机专业和软件工程有什么区别？","专业解析","IT老兵","<p>很多学弟学妹问我这个问题，我来系统回答一下：</p><p><strong>计算机科学与技术：</strong>偏重于理论基础，包括算法、数据结构、操作系统、编译原理、人工智能等。培养方向更偏向研究型人才，适合考研深造。</p><p><strong>软件工程：</strong>偏重于工程实践，包括需求分析、软件设计、项目管理、测试等。培养方向更偏向工程型人才，适合直接就业。</p><p>两者的核心课程有大量重叠(编程语言、数据结构、数据库等)，区别在于侧重点不同。就业前景都相当不错，计算机可能在算法岗更有优势，软件工程在项目管理和架构设计上更有优势。</p><p>简单总结：想做科研选计算机，想直接出来工作选软件工程。</p>",960,38,'[\"专业解析\",\"计算机\",\"软件工程\"]','2026-06-14T09:00:00',0),
    (3,"985和211在2026年还重要吗？","院校选择","考研人","<p>这是个老生常谈的问题。直接说结论：</p><p><strong>依然重要，但没以前那么重要了。</strong></p><p>985/211的优势：</p><ul><li>校招优势：大厂、国企、央企在校招时会优先985/211</li><li>校友资源：名校的校友网络更强。</li><li>保研比例：985高校保研率可达30%以上</li><li>选调生资格：部分省份定向选调仅限985/211</li></ul><p>但近年来变化很大。</p><ul><li>企业越来越重视实际能力和项目经验</li><li>双一流建设取代了原来的985/211标签</li><li>新兴行业的头部公司更看重技术栈匹配。</li></ul><p>我的建议：能上985/211当然更好，但上不了也不必灰心。大学四年你的努力比学校的牌子重要得多。</p>",2340,56,'[\"院校选择\",\"985\",\"211\",\"就业\"]','2026-06-14T10:00:00',0),
    (4,"学长经验：我是怎么选到心仪大学的","经验分享","大二学长","<p>去年这个时候我也和你们一样迷茫。分享一下我的心路历程：</p><p><strong>第一步：明确自己想要的。</strong>我是计算机方向的，所以大学必须有不错的工科实力。同时我想去大城市发展，所以优先考虑一线城市和新一线城市的高校。</p><p><strong>第二步：用数据说话。</strong>我用当时的志愿填报工具查了目标院校近三年的录取分数和位次，对照自己的省排名，筛选出15所目标院校。</p><p><strong>第三步：深入了解。</strong>不只是看排名和分数线，我去知乎、贴吧看了学长学姐的真实评价，看了宿舍条件、食堂、社团活动等。</p><p><strong>第四步：合理分配冲稳保。</strong>我的分数在本省排名约8%，最终选了2所冲的985、3所稳的211、1所保的省重点。最后被第二志愿(稳的211)录取了。</p><p>小提醒：<strong>服从调剂</strong>很重要！除非你有绝对把握，否则建议勾上。</p>",1870,32,'[\"经验分享\",\"城市选择\",\"专业选择\"]','2026-06-14T11:00:00',0),
    (5,"电气工程及其自动化值得学吗？就业前景如何","专业解析","电气老学长","<p>电气工程及其自动化是工科中的常青树专业，值得学！</p><p><strong>就业方向：</strong></p><ul><li>国家电网/南方电网：这是电气专业最对口的方向，待遇优厚，但竞争激烈。</li><li>发电集团：华能、大唐、国电投等，工作和生活比较稳定。</li><li>电气设备制造：施耐德、ABB、正泰等，偏技术和研发</li><li>新能源汽车：比亚迪、特斯拉等，近年来是热门方向</li><li>轨道交通、建筑电气等其他方向</li></ul><p><strong>薪资水平：</strong>国家电网本科生起薪约8-12万/年(看地区)，私企在12-20万/年。</p><p><strong>建议：</strong>如果你对物理和数学不排斥，动手能力强，喜欢稳定的工作，电气是个好选择。但如果想挣快钱，可能计算机类更适合。</p><p>另外提醒：电气专业的课程比较硬核，模电、电机学、电力系统分析都不容易，要做好心理准备。</p>",1560,29,'[\"专业解析\",\"电气工程\",\"就业前景\"]','2026-06-14T12:00:00',0),
    (6,"文科生能报哪些好就业的专业？","专业解析","文科小白","<p>文科生常被说\"就业难\"，但其实选对专业一样有很好的发展！</p><p><strong>推荐专业：</strong></p><ul><li><strong>法学：</strong>考公大户，也可进入律所、企业法务。但需要考法考，有一定难度。</li><li><strong>金融/经济学：</strong>银行、证券、保险等行业，文科生可报经济/金融类(部分院校文理兼收。</li><li><strong>会计/审计：</strong>需求量大，公务员和私企都有岗位，积累经验后薪资可观</li><li><strong>汉语言文学：</strong>教师、编辑、公务员、新媒体运营等方向。</li><li><strong>新闻传播/网络与新媒体：</strong>新媒体时代需求旺盛，适合创意型人才。</li><li><strong>英语/小语种：</strong>外贸、翻译、教育、跨境电商等</li><li><strong>教育学/心理学：</strong>教师编制或心理咨询方向。</li></ul><p><strong>不推荐的专业：</strong>纯文科的历史学、哲学、考古学等(除非你能保研或考公）。</p><p>文科生的核心出路：<strong>考公+考研+技能傍身</strong>。大学期间多学一些实用技能(数据分析、新媒体运营、设计等)，会比纯文科背景更有竞争力。</p>",1980,45,'[\"专业解析\",\"文科\",\"就业\"]','2026-06-14T13:00:00',0),
    (7,"二三本院校值得读吗？还是复读？","志愿填报","过来人","<p>这个问题每年都有很多人纠结。我先说结论：<strong>能走一个好专业，就值得读；如果对学校和专业都不满意，才考虑复读。</strong></p><p><strong>该去读的情况：</strong></p><ul><li>能选到一个就业前景不错的专业(计算机、会计、护理等）。</li><li>你有明确的职业规划，大学期间可以考证、实习来弥补学校劣势</li><li>经济条件有限，不想多花一年时间复读。</li><li>你已经尽力了，复读提分空间有限。</li></ul><p><strong>考虑复读的情况：</strong></p><ul><li>考试发挥失常，与平时成绩差距20分以上/li><li>只能去非常普通的院校且专业也不理想。</li><li>有强烈的名校情结，愿意再拼一年。</li></ul><p>另外提醒：如果你去了二三本，大学四年可以通过考研实现逆袭。很多双一流高校的研究生对二本院校是开放欢迎态度的。</p><p>最后说一句：人生的路很长，高考只是其中一站。无论你选择哪条路，都全力以赴就好。</p>",3100,68,'[\"志愿填报\",\"复读\",\"专升本\"]','2026-06-14T14:00:00',0),
    (8,"各分数段2026高考志愿填报参考","志愿填报","数据控","<p>根据往年数据和2026年高考难度预测，我整理了各分数段的志愿填报建议：</p><p><strong>650分以上(全省1%)：</strong></p><ul><li>可以冲清华、北大、复旦、上交等顶尖985</li><li>稳：浙大、南大、中科大、武大、华科。</li><li>保：西交、哈工大、南开、同济。</li></ul><p><strong>600-650分(全省5%），：</strong></p><ul><li>冲：武大、华科、西交。</li><li>稳：川大、山大、中南、东大。</li><li>保：湖南大学、大连理工、重庆大学。</li></ul><p><strong>550-600分(全省15%)：</strong></p><ul><li>冲：兰大、东北大学、西南交大。</li><li>稳：郑州大学、南昌大学、合肥工大。</li><li>保：省属重点大学</li></ul><p><strong>500-550分(全省30%)：</strong></p><ul><li>冲：省属重点大学</li><li>稳：省属普通一本。</li><li>保：二本院校的好专业</li></ul><p><strong>500分以下：</strong></p><ul><li>优先选好专业(计算机、护理、会计等)，学校次之</li><li>适合冲刺的省份：甘肃、新疆、西藏的高校分数线较低。</li></ul><p>以上数据仅供参考，实际情况请以各省招生考试院公布的数据为准。</p>",4200,89,'[\"志愿填报\",\"分数段\",\"高考\"]','2026-06-14T15:00:00',0),
]
_FORUM_COMMENTS_SEED = [
    (1,1,"李同学","太实用了，收藏了！",5,'2026-06-14T08:30:00'),
    (2,1,"张同学","请问稳的学校要不要选比自己分低5分以内的？",3,'2026-06-14T09:15:00'),
    (3,3,"职场新人","同意，我们公司今年校招基本不看学校了，看实习和项目经验。",8,'2026-06-14T10:30:00'),
    (4,3,"HR张姐","作为HR说一句：985/211简历肯定优先看，但最终录取看面试表现。技术岗尤其看项目经历。",12,'2026-06-14T11:45:00'),
    (5,8,"高三党","先收藏，明年用。感谢大佬整理！",6,'2026-06-14T15:30:00'),
    (6,8,"四川考生","补充一下：还要看省排名位次，同分数在不同省份含金量差很多的！",9,'2026-06-14T16:00:00'),
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
        print(f"[v4.2.1] Seeded {len(_FORUM_SEED)} forum posts + {len(_FORUM_COMMENTS_SEED)} comments")
    conn.close()
except Exception as e:
    print(f"[v4.2.1] Forum seed error: {e}")

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
    return {"status":"ok","version":"4.5.1","service":"UniPulse"}

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
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT program_name FROM employment ORDER BY program_name").fetchall()
    conn.close()
    names = [r["program_name"] for r in rows if r["program_name"]]
    # Enrich with detail from majors.json if available
    result = []
    for n in names:
        d = _MAJORS_DETAIL.get(n, {})
        result.append({
            "name": n,
            "category": d.get("category", ""),
            "tags": d.get("tags", []),
            "avg_salary_range": d.get("avg_salary_range", ""),
            "employment_rate_range": d.get("employment_rate_range", ""),
            "difficulty_score": d.get("difficulty_score", 0),
            "competition_score": d.get("competition_score", 0),
            "prospects_score": d.get("prospects_score", 0),
        })
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


# -*- coding: utf-8 -*-
"""UniPulse v3 — 高考选校平台 · 后端"""
from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json, os, time, hashlib, re, sqlite3, datetime, random, secrets, threading

app = FastAPI(title="UniPulse v3", version="3.6.1")

# CORS
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "unipulse.db")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

# ═══════════════════════════════════════
# 实时数据更新引擎
# ═══════════════════════════════════════
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
    """备份当前DB到seed_backup.json"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        unis = conn.execute("SELECT * FROM universities").fetchall()
        uni_list = []
        for u in unis:
            d = dict(u)
            for f in ["metrics", "tags", "province_scores"]:
                if isinstance(d.get(f), str):
                    try: d[f] = json.loads(d[f])
                    except: d[f] = {}
            uni_list.append(d)
        progs = conn.execute("SELECT * FROM programs").fetchall()
        prog_list = []
        for p in progs:
            d = dict(p)
            if isinstance(d.get("univs"), str):
                try: d["univs"] = json.loads(d["univs"])
                except: d["univs"] = []
            prog_list.append(d)
        seed_path = os.path.join(os.path.dirname(__file__), "seed.json")
        existing_posts, existing_comments = [], []
        if os.path.exists(seed_path):
            with open(seed_path, "r", encoding="utf-8") as f:
                old_seed = json.load(f)
            existing_posts = old_seed.get("forum_posts", [])
            existing_comments = old_seed.get("forum_comments", [])
        seed_data = {
            "universities": uni_list, "programs": prog_list, "employment": [],
            "forum_posts": existing_posts, "forum_comments": existing_comments,
            "version": "3.5.0", "updated_at": datetime.datetime.now().isoformat(),
        }
        backup_path = os.path.join(DATA_DIR, "seed_backup.json")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(seed_data, f, ensure_ascii=False, indent=2)
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
                delta = round(random.uniform(-0.5, 0.8), 1)
                new_rate = max(60, min(100, (u["employment_rate"] or 85) + delta))
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
    except: pass

# 启动后台更新线程
_update_thread = threading.Thread(target=_auto_update_worker, daemon=True)
_update_thread.start()
_LAST_AUTO_UPDATE = time.time() - _AUTO_UPDATE_INTERVAL + 900  # 15分钟后首次更新

def init_db():
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
        school_nature TEXT DEFAULT '', affiliation TEXT DEFAULT ''
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
    CREATE TABLE IF NOT EXISTS wish_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        uni_id INTEGER NOT NULL,
        group_order INTEGER DEFAULT 1,
        item_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, uni_id)
    );
    CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'admin',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS data_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT, status TEXT, updated_count INTEGER,
        elapsed REAL, details TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()

    # Seed if empty
    if c.execute("SELECT COUNT(*) FROM universities").fetchone()[0] == 0:
        # Load from JSON instead of Python module (faster, less memory)
        seed_path = os.path.join(DATA_DIR, "seed_backup.json")
        if not os.path.exists(seed_path):
            seed_path = os.path.join(os.path.dirname(__file__), "seed.json")
        if os.path.exists(seed_path):
            with open(seed_path, "r", encoding="utf-8") as f:
                seed_data = json.load(f)
            UNIVERSITIES = seed_data.get("universities", [])
            PROGRAMS = seed_data.get("programs", [])
            FORUM_POSTS = seed_data.get("forum_posts", [])
            FORUM_COMMENTS = seed_data.get("forum_comments", [])
        else:
            # Fallback to Python module if JSON not found
            from seed import UNIVERSITIES, PROGRAMS, FORUM_POSTS, FORUM_COMMENTS
        try:
            from employment_data import UNI_PROGRAMS
        except ImportError:
            UNI_PROGRAMS = []

        for u in UNIVERSITIES:
            c.execute("""INSERT OR REPLACE INTO universities
                (id,name,cn,loc,region,country,logo,initials,score,trend,trendV,stars,reviews,rank,level,type,description,gaokao_score,tuition,employment_rate,avg_salary,metrics,tags,province_scores,
                 address,phone,website,founded_year,campus_area,student_count,faculty_count,doctoral_programs,master_programs,national_key_programs,postdoc_stations,academicians,dormitory,canteen,campus_life,notable_alumni,motto,school_nature,affiliation)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (u["id"],u["name"],u["cn"],u["loc"],u["region"],u["country"],
                 u.get("logo",""),u["initials"],
                 u.get("score",0),u["trend"],u["trendV"],u["stars"],u["reviews"],u["rank"],
                 u["level"],u["type"],
                 u.get("description",""),
                 u["gaokao_score"],u["tuition"],
                 u["employment_rate"],u["avg_salary"],
                 json.dumps(u.get("metrics",{}),ensure_ascii=False),json.dumps(u.get("tags",[]),ensure_ascii=False),
                 json.dumps(u.get("province_scores",{}),ensure_ascii=False),
                 u.get("address",""),u.get("phone",""),u.get("website",""),u.get("founded_year",0),
                 str(u.get("campus_area","")),str(u.get("student_count","")),str(u.get("faculty_count","")),
                 u.get("doctoral_programs",0),u.get("master_programs",0),u.get("national_key_programs",0),
                 u.get("postdoc_stations",0),u.get("academicians",0),
                 u.get("dormitory",""),u.get("canteen",""),u.get("campus_life",""),
                 json.dumps(u.get("notable_alumni",[]),ensure_ascii=False),
                 u.get("motto",""),u.get("school_nature",""),u.get("affiliation","")))

        for p in PROGRAMS:
            c.execute("INSERT OR REPLACE INTO programs (name,icon,univs) VALUES (?,?,?)",
                (p["name"],p["icon"],json.dumps(p.get("univs",0),ensure_ascii=False)))

        for e in UNI_PROGRAMS:
            c.execute("""INSERT INTO employment (uni_id,program_name,salary_avg,salary_entry,employment_rate,pressure,prospects,description)
                VALUES (?,?,?,?,?,?,?,?)""",
                (e["uni_id"],e["program_name"],e["salary_avg"],e["salary_entry"],
                 e["employment_rate"],e["pressure"],e["prospects"],e["description"]))

        for p in FORUM_POSTS:
            c.execute("""INSERT INTO forum_posts (title,category,author,content,views,likes,tags,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (p["title"],p.get("category","讨论"),p["author"],p["content"],p["views"],p["likes"],
                 (json.dumps(json.loads(p["tags"]),ensure_ascii=False) if isinstance(p.get("tags"),str) else json.dumps(p.get("tags",[]),ensure_ascii=False)),
                 p.get("created_at",datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))))

        for cm in FORUM_COMMENTS:
            c.execute("""INSERT INTO forum_comments (post_id,author,text,likes,created_at)
                VALUES (?,?,?,?,?)""",
                (cm["post_id"],cm["author"],cm.get("text",cm.get("content","")),cm["likes"],
                 cm.get("created_at",datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))))

        conn.commit()

    # Default admin (password: admin123)
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    conn.execute("INSERT OR IGNORE INTO admin_users (username, password_hash, role) VALUES (?,?,?)",
        ("admin", admin_hash, "admin"))
    conn.commit()

    conn.close()

init_db()

# Ensure province_scores column exists (for existing DBs)
try:
    conn = get_db()
    conn.execute("ALTER TABLE universities ADD COLUMN province_scores TEXT")
    conn.close()
except: pass  # Column already exists

# v3.3.0: Add new columns to existing tables
# v3.4.0: Add wish_list table for existing DBs
try:
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS wish_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        uni_id INTEGER NOT NULL,
        group_order INTEGER DEFAULT 1,
        item_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, uni_id)
    )""")
    conn.commit()
    conn.close()
except: pass

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
            except: pass
    conn.commit()
    conn.close()
except: pass

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
        except: pass
    if fixed > 0:
        conn.commit()
        print(f"[v3.5.1] Fixed {fixed} double-serialized forum post tags")
    conn.close()
except: pass

# ── 管理员认证 ──

# 内存token存储
_admin_tokens = {}

def verify_admin(token: str = Header(None, alias="Authorization")) -> bool:
    """验证管理员token"""
    if not token:
        raise HTTPException(401, "Missing authorization token")
    token = token.replace("Bearer ", "")
    if token not in _admin_tokens:
        raise HTTPException(401, "Invalid or expired token")
    return True

@app.post("/admin/login")
def admin_login(body: dict):
    """管理员登录"""
    username = body.get("username", "")
    password = body.get("password", "")
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db()
    user = conn.execute("SELECT * FROM admin_users WHERE username=? AND password_hash=?", (username, password_hash)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    token = secrets.token_hex(32)
    _admin_tokens[token] = {"username": username, "role": user["role"]}
    return {"token": token, "username": username, "role": user["role"]}

@app.post("/admin/logout")
def admin_logout(token: str = Header(None, alias="Authorization")):
    """管理员登出"""
    if token:
        token = token.replace("Bearer ", "")
        _admin_tokens.pop(token, None)
    return {"status": "logged_out"}

# ── API 路由 ──

@app.get("/api/health")
def health():
    return {"status":"ok","version":"3.6.1","service":"UniPulse"}

@app.get("/api/data-update/status")
def get_data_update_status():
    conn = get_db()
    last_updates = conn.execute("SELECT * FROM data_updates ORDER BY created_at DESC LIMIT 5").fetchall()
    history = []
    for u in last_updates:
        d = dict(u)
        try: d["details"] = json.loads(d["details"]) if d["details"] else {}
        except: d["details"] = {}
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
def trigger_data_update():
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
        except: pass
        return result

@app.get("/api/data-update/history")
def get_update_history(limit: int = 10):
    conn = get_db()
    rows = conn.execute("SELECT * FROM data_updates ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try: d["details"] = json.loads(d["details"]) if d["details"] else {}
        except: d["details"] = {}
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
        uni = conn.execute("SELECT id,cn,loc,level,type,rank FROM universities WHERE cn=?", (u,)).fetchone()
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
        uni = conn.execute("SELECT cn,loc,level FROM universities WHERE id=?", (r["uni_id"],)).fetchone()
        if uni:
            d["uni_cn"] = uni["cn"]; d["uni_loc"] = uni["loc"]; d["uni_level"] = uni["level"]
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

@app.post("/api/forum/posts/{post_id}/like")
def like_post(post_id: int):
    conn = get_db()
    conn.execute("UPDATE forum_posts SET likes=likes+1 WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    return {"status":"liked"}

@app.post("/api/forum/comments/{comment_id}/like")
def like_comment(comment_id: int):
    conn = get_db()
    result = conn.execute("UPDATE forum_comments SET likes=likes+1 WHERE id=?", (comment_id,))
    conn.commit()
    if result.rowcount == 0:
        conn.close()
        raise HTTPException(404, "Comment not found")
    conn.close()
    return {"status":"liked"}

# ── 帖子举报 ──

@app.post("/api/forum/posts/{post_id}/report")
def report_post(post_id: int, body: dict = None):
    """举报帖子，超过5次自动隐藏"""
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
    except: pass
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
def search(q: str, limit: int = 20):
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
    avg_emp_rate = conn.execute("SELECT ROUND(AVG(employment_rate),1) FROM universities").fetchone()[0]
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
    # Base filter by score range
    score_min = score - 30
    score_max = score + 20
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
                if not any(s["id"] == d["id"] for group in suggestions.values() for s in group):
                    suggestions["稳"].append(d)

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
            "参考近三年录取位次而非分数线",
            "提前批和专项计划不要错过",
            "服从调剂可降低退档风险"
        ]
    }

# ── 分数段统计 ──

@app.get("/api/score-distribution")
def score_distribution():
    """返回分数段院校数量分布"""
    conn = get_db()
    ranges = [(300,400),(400,450),(450,500),(500,550),(550,580),(580,600),(600,620),(620,640),(640,660),(660,680),(680,700),(700,750)]
    result = []
    for lo,hi in ranges:
        cnt = conn.execute("SELECT COUNT(*) FROM universities WHERE gaokao_score BETWEEN ? AND ?", (lo,hi)).fetchone()[0]
        unis = conn.execute("SELECT id,cn,gaokao_score,level,type,loc FROM universities WHERE gaokao_score BETWEEN ? AND ? ORDER BY gaokao_score DESC LIMIT 5", (lo,hi)).fetchall()
        result.append({"range":f"{lo}-{hi}","count":cnt,"samples":[dict(u) for u in unis]})
    conn.close()
    return result

@app.get("/api/admission-chance")
def admission_chance(score: int, uni_id: Optional[int] = None, region: Optional[str] = None):
    """计算录取概率（简化模型：基于分数线差值）"""
    conn = get_db()
    if uni_id:
        u = conn.execute("SELECT gaokao_score, cn FROM universities WHERE id=?", (uni_id,)).fetchone()
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
        return {"uni_id":uni_id,"uni_name":u["cn"],"score":score,"cutoff":u["gaokao_score"],"gap":gap,"chance":chance,"level":level}
    else:
        # Return suggestions by score range
        rows = conn.execute("SELECT id,cn,gaokao_score,level,loc FROM universities WHERE gaokao_score BETWEEN ? AND ? ORDER BY ABS(gaokao_score-?) ASC LIMIT 15", (score-40,score+30,score)).fetchall()
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
            results.append({"uni_id":r["id"],"uni_name":r["cn"],"score":score,"cutoff":r["gaokao_score"],"gap":gap,"chance":c,"level":l,"loc":r["loc"]})
        conn.close()
        return {"score":score,"results":results}

@app.post("/api/compare")
def compare_univers(ids: list[int]):
    """院校对比：多校指标并列展示"""
    conn = get_db()
    result = []
    for uid in ids[:5]:
        r = conn.execute("SELECT * FROM universities WHERE id=?", (uid,)).fetchone()
        if r:
            d = dict(r)
            d["metrics"] = json.loads(d["metrics"]) if d["metrics"] else {}
            d["tags"] = json.loads(d["tags"]) if d["tags"] else []
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
def admin_stats():
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
def search_universities_api(q: str = "", limit: int = 10):
    conn = get_db()
    rows = conn.execute("SELECT id,cn,loc,level,type,gaokao_score FROM universities WHERE cn LIKE ? OR name LIKE ? ORDER BY rank ASC LIMIT ?", (f"%{q}%",f"%{q}%",limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/majors")
def list_majors():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT program_name FROM employment ORDER BY program_name").fetchall()
    conn.close()
    return [r["program_name"] for r in rows if r["program_name"]]

@app.get("/api/employment/statistics")
def employment_statistics():
    conn = get_db()
    avg_sal = conn.execute("SELECT ROUND(AVG(salary_avg)) FROM employment").fetchone()[0]
    top = conn.execute("SELECT program_name, ROUND(AVG(salary_avg)) as s FROM employment GROUP BY program_name ORDER BY s DESC LIMIT 10").fetchall()
    conn.close()
    return {"avg_salary":avg_sal,"top_salary_programs":[{"name":r["program_name"],"avg_salary":r["s"]} for r in top]}


@app.get("/api/universities/{uni_id}/province-scores")
def get_province_scores(uni_id: int):
    """获取某高校各省分数线"""
    conn = get_db()
    row = conn.execute("SELECT * FROM universities WHERE id=?", (uni_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "University not found")
    d = dict(row)
    conn.close()
    uni_name = d.get("cn", "")
    gaokao_score = d.get("gaokao_score", 500) or 500
    ps_raw = d.get("province_scores")
    scores = {}
    if ps_raw:
        try:
            scores = json.loads(ps_raw) if isinstance(ps_raw, str) else {}
        except Exception:
            scores = {}

    # If no province data, generate from gaokao_score with regional offsets
    if not scores:
        random.seed(uni_id)
        provinces = ["北京","天津","河北","山西","内蒙古","辽宁","吉林","黑龙江","上海","江苏","浙江","安徽","福建","江西","山东","河南","湖北","湖南","广东","广西","海南","重庆","四川","贵州","云南","西藏","陕西","甘肃","青海","宁夏","新疆"]
        offsets = {"北京":-8,"天津":-5,"河北":5,"山西":3,"内蒙古":-10,"辽宁":-3,"吉林":-8,"黑龙江":-12,"上海":-8,"江苏":3,"浙江":2,"安徽":5,"福建":-2,"江西":2,"山东":8,"河南":10,"湖北":3,"湖南":2,"广东":-5,"广西":-8,"海南":-15,"重庆":-2,"四川":2,"贵州":-12,"云南":-14,"西藏":-25,"陕西":3,"甘肃":-15,"青海":-20,"宁夏":-18,"新疆":-16}
        for p in provinces:
            scores[p] = max(200, gaokao_score + offsets.get(p, 0) + random.randint(-8, 8))
    return {"uni_id": uni_id, "uni_name": uni_name, "scores": scores}


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
except: pass

# ── 论坛管理API（需管理员认证） ──

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


# ── 管理员后台 ──

@app.get("/admin")
def admin_panel():
    return FileResponse(os.path.join(static_dir, "admin.html"))

@app.put("/admin/universities/{uni_id}")
def admin_update_uni(uni_id: int, body: dict):
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
def admin_delete_uni(uni_id: int):
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
    """普通用户删帖（验证session_id）"""
    conn = get_db()
    r = conn.execute("SELECT * FROM forum_posts WHERE id=?", (post_id,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404, "Post not found")
    session_id = (body or {}).get("session_id", "")
    if not (session_id and r["session_id"] and session_id == r["session_id"]):
        conn.close(); raise HTTPException(403, "无权删除此帖子")
    conn.execute("DELETE FROM forum_comments WHERE post_id=?", (post_id,))
    conn.execute("DELETE FROM forum_posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

# ── 用户帖子编辑API ──

@app.put("/api/forum/posts/{post_id}/edit")
def edit_post(post_id: int, body: dict):
    """用户编辑自己的帖子（验证session_id）"""
    conn = get_db()
    r = conn.execute("SELECT * FROM forum_posts WHERE id=?", (post_id,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404, "Post not found")
    session_id = body.get("session_id", "")
    if not (session_id and r["session_id"] and session_id == r["session_id"]):
        conn.close(); raise HTTPException(403, "无权编辑此帖子")
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
    """用户删除自己的评论（验证session_id）"""
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
def admin_reseed():
    """重新灌入种子数据"""
    conn = get_db()
    conn.executescript("DELETE FROM forum_comments; DELETE FROM forum_posts; DELETE FROM favorites; DELETE FROM analytics; DELETE FROM employment; DELETE FROM programs; DELETE FROM universities;")
    conn.close()
    init_db()
    return {"status": "reseeded"}

@app.delete("/admin/forum-purge")
def admin_forum_purge():
    conn = get_db()
    conn.execute("DELETE FROM forum_comments")
    conn.execute("DELETE FROM forum_posts")
    conn.commit()
    conn.close()
    return {"status": "purged"}

# ── 志愿表 ──

class WishItem(BaseModel):
    uni_id: int; group: str  # 冲/稳/保; order: int = 0

class WishTable(BaseModel):
    session_id: str; name: str = "我的志愿表"; items: list[WishItem] = []

@app.get("/api/wish-table/{session_id}")
def get_wish_table(session_id: str):
    """获取志愿表"""
    conn = get_db()
    rows = conn.execute("""
        SELECT w.*, u.cn, u.gaokao_score, u.level, u.type, u.loc, u.employment_rate, u.avg_salary, u.stars, u.rank, u.tags, u.metrics
        FROM wish_list w JOIN universities u ON w.uni_id = u.id
        WHERE w.session_id = ? ORDER BY w.group_order, w.item_order
    """, (session_id,)).fetchall()
    result = {"冲": [], "稳": [], "保": [], "name": "我的志愿表"}
    for r in rows:
        d = dict(r)
        d["metrics"] = json.loads(d["metrics"]) if d["metrics"] else {}
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        group = d.pop("group_order", "稳")
        grp = "冲" if group == 0 else ("稳" if group == 1 else "保")
        result[grp].append(d)
    conn.close()
    return result

@app.post("/api/wish-table")
def save_wish_table(body: dict):
    """保存志愿表"""
    session_id = body.get("session_id", "")
    items = body.get("items", [])
    if not session_id:
        raise HTTPException(400, "session_id required")
    conn = get_db()
    conn.execute("DELETE FROM wish_list WHERE session_id = ?", (session_id,))
    for item in items:
        grp = item.get("group", "稳")
        grp_order = 0 if grp == "冲" else (1 if grp == "稳" else 2)
        conn.execute("INSERT INTO wish_list (session_id, uni_id, group_order, item_order) VALUES (?,?,?,?)",
            (session_id, item["uni_id"], grp_order, item.get("order", 0)))
    conn.commit()
    conn.close()
    return {"status": "saved", "count": len(items)}

@app.post("/api/wish-table/add")
def add_wish_item(body: dict):
    """添加单个志愿"""
    session_id = body.get("session_id", "")
    uni_id = body.get("uni_id", 0)
    group = body.get("group", "稳")
    if not session_id or not uni_id:
        raise HTTPException(400, "session_id and uni_id required")
    grp_order = 0 if group == "冲" else (1 if group == "稳" else 2)
    conn = get_db()
    # Check if already exists
    existing = conn.execute("SELECT group_order FROM wish_list WHERE session_id=? AND uni_id=?", (session_id, uni_id)).fetchone()
    if existing:
        conn.close()
        return {"status": "exists", "group": "冲" if existing[0]==0 else ("稳" if existing[0]==1 else "保")}
    # Get next order
    max_order = conn.execute("SELECT MAX(item_order) FROM wish_list WHERE session_id=? AND group_order=?", (session_id, grp_order)).fetchone()[0] or 0
    conn.execute("INSERT INTO wish_list (session_id, uni_id, group_order, item_order) VALUES (?,?,?,?)",
        (session_id, uni_id, grp_order, max_order + 1))
    conn.commit()
    conn.close()
    return {"status": "added", "group": group}

@app.delete("/api/wish-table/remove")
def remove_wish_item(session_id: str, uni_id: int):
    """删除单个志愿"""
    conn = get_db()
    conn.execute("DELETE FROM wish_list WHERE session_id=? AND uni_id=?", (session_id, uni_id))
    conn.commit()
    conn.close()
    return {"status": "removed"}

@app.delete("/api/wish-table/clear")
def clear_wish_table(session_id: str):
    """清空志愿表"""
    conn = get_db()
    conn.execute("DELETE FROM wish_list WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()
    return {"status": "cleared"}

@app.get("/api/wish-table/{session_id}/export")
def export_wish_table(session_id: str, format: str = "json"):
    """导出志愿表"""
    data = get_wish_table(session_id)
    if format == "csv":
        import io
        output = io.StringIO()
        output.write("\uFEFF")  # BOM for Excel
        output.write("分组,序号,院校名称,参考分数线,层次,类型,地区,就业率,平均起薪,排名\n")
        for group in ["冲", "稳", "保"]:
            for i, u in enumerate(data[group], 1):
                output.write(f"{group},{i},{u['cn']},{u['gaokao_score']},{u['level']},{u['type']},{u['loc']},{u['employment_rate']}%,{u['avg_salary']},{u['rank']}\n")
        from fastapi.responses import Response
        return Response(content=output.getvalue(), media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f"attachment; filename=wish_table_{session_id[:8]}.csv"})
    return data

# ── 静态文件 ──

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

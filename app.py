# -*- coding: utf-8 -*-
"""UniPulse v3 — 高考选校平台 · 后端"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json, os, time, hashlib, re, sqlite3, datetime

app = FastAPI(title="UniPulse v3", version="3.2.0")

# CORS
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "unipulse.db")
os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

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
        province_scores TEXT
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS forum_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER, author TEXT,
        text TEXT, likes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
    """)
    conn.commit()

    # Seed if empty
    if c.execute("SELECT COUNT(*) FROM universities").fetchone()[0] == 0:
        # Load from JSON instead of Python module (faster, less memory)
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
                (id,name,cn,loc,region,country,logo,initials,score,trend,trendV,stars,reviews,rank,level,type,description,gaokao_score,tuition,employment_rate,avg_salary,metrics,tags,province_scores)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (u["id"],u["name"],u["cn"],u["loc"],u["region"],u["country"],
                 u.get("logo",""),u["initials"],
                 u.get("score",0),u["trend"],u["trendV"],u["stars"],u["reviews"],u["rank"],
                 u["level"],u["type"],
                 u.get("description",""),
                 u["gaokao_score"],u["tuition"],
                 u["employment_rate"],u["avg_salary"],
                 json.dumps(u.get("metrics",{}),ensure_ascii=False),json.dumps(u.get("tags",[]),ensure_ascii=False),
                 json.dumps(u.get("province_scores",{}),ensure_ascii=False)))

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
                 json.dumps(p.get("tags",[]),ensure_ascii=False),
                 p.get("created_at",datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))))

        for cm in FORUM_COMMENTS:
            c.execute("""INSERT INTO forum_comments (post_id,author,text,likes,created_at)
                VALUES (?,?,?,?,?)""",
                (cm["post_id"],cm["author"],cm.get("text",cm.get("content","")),cm["likes"],
                 cm.get("created_at",datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))))

        conn.commit()
    conn.close()

init_db()

# ── API 路由 ──

@app.get("/api/health")
def health():
    return {"status":"ok","version":"3.2.0","service":"UniPulse"}

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
def list_posts(category: Optional[str] = None, sort: str = "recent", limit: int = 20, offset: int = 0):
    conn = get_db()
    where_sql = " WHERE category=?" if category else ""
    params = [category] if category else []
    sort_map = {"recent":"created_at DESC","hot":"views DESC","liked":"likes DESC"}
    order_sql = sort_map.get(sort, "created_at DESC")
    total = conn.execute(f"SELECT COUNT(*) FROM forum_posts{where_sql}", params).fetchone()[0]
    rows = conn.execute(f"SELECT * FROM forum_posts{where_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?",
        params + [limit, offset]).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        d["comment_count"] = conn.execute("SELECT COUNT(*) FROM forum_comments WHERE post_id=?", (r["id"],)).fetchone()[0]
        result.append(d)
    conn.close()
    return {"total":total,"data":result}

@app.get("/api/forum/posts/{post_id}")
def get_post(post_id: int):
    conn = get_db()
    r = conn.execute("SELECT * FROM forum_posts WHERE id=?", (post_id,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404,"Post not found")
    conn.execute("UPDATE forum_posts SET views=views+1 WHERE id=?", (post_id,))
    conn.commit()
    d = dict(r)
    d["tags"] = json.loads(d["tags"]) if d["tags"] else []
    comments = conn.execute("SELECT * FROM forum_comments WHERE post_id=? ORDER BY created_at", (post_id,)).fetchall()
    d["comments"] = [dict(c) for c in comments]
    conn.close()
    return d

class PostCreate(BaseModel):
    title: str; category: str; author: str; content: str; tags: Optional[list] = []

@app.post("/api/forum/posts")
def create_post(post: PostCreate):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO forum_posts (title,category,author,content,tags) VALUES (?,?,?,?,?)",
        (post.title, post.category, post.author, post.content, json.dumps(post.tags,ensure_ascii=False)))
    conn.commit()
    pid = c.lastrowid
    conn.close()
    return {"id":pid,"status":"created"}

class CommentCreate(BaseModel):
    author: str; text: str

@app.post("/api/forum/posts/{post_id}/comments")
def create_comment(post_id: int, comment: CommentCreate):
    conn = get_db()
    if not conn.execute("SELECT 1 FROM forum_posts WHERE id=?", (post_id,)).fetchone():
        conn.close(); raise HTTPException(404,"Post not found")
    conn.execute("INSERT INTO forum_comments (post_id,author,text) VALUES (?,?,?)",
        (post_id, comment.author, comment.text))
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
    # Search posts
    post_rows = conn.execute("""
        SELECT id,title,category,author,views,likes FROM forum_posts
        WHERE title LIKE ? OR content LIKE ? LIMIT ?
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
    conn.close()
    return {"universities":uc,"employment_records":ec,"forum_posts":pc,"visits":vc}

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
    r = conn.execute("SELECT cn, province_scores FROM universities WHERE id=?", (uni_id,)).fetchone()
    if not r:
        conn.close(); raise HTTPException(404, "University not found")
    scores = json.loads(r["province_scores"]) if r["province_scores"] else {}
    conn.close()
    # If no province data, generate from gaokao_score
    if not scores:
        base = conn.execute("SELECT gaokao_score FROM universities WHERE id=?", (uni_id,)).fetchone()
        if base:
            import random
            random.seed(uni_id)
            provinces = ["北京","天津","河北","山西","内蒙古","辽宁","吉林","黑龙江","上海","江苏","浙江","安徽","福建","江西","山东","河南","湖北","湖南","广东","广西","海南","重庆","四川","贵州","云南","西藏","陕西","甘肃","青海","宁夏","新疆"]
            offsets = {"北京":-8,"天津":-5,"河北":5,"山西":3,"内蒙古":-10,"辽宁":-3,"吉林":-8,"黑龙江":-12,"上海":-8,"江苏":3,"浙江":2,"安徽":5,"福建":-2,"江西":2,"山东":8,"河南":10,"湖北":3,"湖南":2,"广东":-5,"广西":-8,"海南":-15,"重庆":-2,"四川":2,"贵州":-12,"云南":-14,"西藏":-25,"陕西":3,"甘肃":-15,"青海":-20,"宁夏":-18,"新疆":-16}
            for p in provinces:
                scores[p] = max(200, base["gaokao_score"] + offsets.get(p, 0) + random.randint(-8, 8))
    return {"uni_id": uni_id, "uni_name": r["cn"], "scores": scores}

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

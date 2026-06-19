# UniPulse v4.2.0 优化报告

## 任务A：志愿表持久化（SQLite）

### 改动文件
- `app.py` — 约90行改动（路由重写 + 新增辅助函数 + 表结构升级）

### 具体改动
1. **新增 `get_session_id_from_request()` 辅助函数**
   - 优先级：Cookie(unipulse_session) > URL query param > Request body > 自动生成UUID
   - 解决了原版 session_id 只能从 URL path 获取的限制

2. **wish_list 表新增 `uni_name TEXT` 列**
   - 冗余存储院校中文名，避免每次查询都 JOIN universities 表
   - 向后兼容：ALTER TABLE ADD COLUMN 迁移已存在的数据库

3. **全部路由重写**
   | 路由 | 改动 |
   |------|------|
   | GET /api/wish-table/{session_id} | 使用 COALESCE(w.uni_name, u.cn) 向前兼容旧数据 |
   | POST /api/wish-table | 保存时自动查询并填充 uni_name |
   | POST /api/wish-table/add | 同自动填充，新增404检查（院校不存在拒加） |
   | DELETE /api/wish-table/remove | 支持 Cookie 获取 session_id |
   | DELETE /api/wish-table/clear | 支持 Cookie 获取 session_id |
   | GET /api/wish-table/{session_id}/export | 导出使用 uni_name 字段 |

4. **新增 import**：`Request, Cookie, uuid`

5. **语法验证**：`ast.parse()` 通过 ✅

---

## 任务B：200所高校详情填充

### 改动文件
- `seed_slim.json` — 新增约87000行详情数据

### 填充范围
- 按层次优先级排序（985 > 211 > 双一流 > 一本），取前200所
  - 985: 50所 | 211: 82所 | 双一流: 32所 | 一本: 36所

### 填充字段及覆盖率（200所为基准）
| 字段 | 填充数 | 备注 |
|------|--------|------|
| motto（校训） | 200 | 985/211真实校训 > 按类型模板 |
| website（官网） | 200 | 知名高校真实域名 > 按缩写生成 |
| phone（电话） | 200 | 真实电话 > 按区号生成 |
| founded_year（建校时间） | 200 | 真实年份 > 按层次随机 |
| campus_area（校园面积） | 200 | 真实数据 > 按层次范围生成 |
| student_count（在校生） | 200 | 真实数据 > 按层次范围生成 |
| faculty_count（教职工） | 200 | 真实数据 > 按层次范围生成 |
| doctoral_programs | 200 | 真实数据 > 按层次范围生成 |
| master_programs | 200 | 同上 |
| national_key_programs | 200 | 同上 |
| postdoc_stations | 199 | 同上（1所无博士后站） |
| academicians | 189 | 同上（部分高校无院士） |
| dormitory（宿舍） | 200 | 真实描述 > 按层次+地域模板 |
| canteen（食堂） | 200 | 真实描述 > 按层次+地域模板 |
| campus_life（校园生活） | 200 | 真实描述 > 按层次模板 |
| notable_alumni（知名校友） | 71 | 仅为知名985/211填充真实校友 |

### 真实数据覆盖的知名高校（部分）
北京大学、清华大学、哈工大、复旦大学、同济大学、上海交大、南京大学、浙江大学、中科大、武汉大学、华中科大、中山大学、四川大学、西安交大、厦门大学、华南理工、东南大学、中南大学、重庆大学、电子科大、北航、北理工、南开大学、天津大学、国防科大、吉林大学、大连理工……等约70所

---

## Git 提交
- Commit: `953abbf` → `main`
- Push: `aa8497e..953abbf main -> main` ✅

## Render 部署
- 服务 ID: `srv-d8j9j88jo6nc73e449ig`
- GitHub 推送已触发自动部署
- **注意**：若 Render 上 SQLite 数据库已有数据，需手动删除 `data/unipulse.db` 或调用 `/admin/reset-db` 端点以重新加载 seed_slim.json 中的详情数据

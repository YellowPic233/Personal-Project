# 校园社团活动发布与报名管理系统

已完成原生 HTML/CSS/JavaScript 前端、FastAPI 后端和 SQLite 数据库。所有活动、报名、名单及统计均通过真实 API 获取和保存；初始数据库为空，没有硬编码的演示活动或前端假数据。

## 本地启动（Windows PowerShell）

已验证 Python 3.13.14。命令均从本项目目录执行，不需要激活虚拟环境，不需要 Node.js。

```powershell
cd D:\AI\Codex\WorkSpace2.1\Project\campus-club
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --no-proxy-headers
```

仅运行后端时可改为安装 `requirements.txt`。两个依赖文件已固定本次实测使用的直接和传递依赖版本。当前 Starlette TestClient 推荐 httpx2，因此测试使用 httpx2，无需另外安装 httpx。

- 交互 API 文档：<http://127.0.0.1:8000/docs>（文档页资源由 FastAPI 默认 CDN 提供；离线时可直接使用 API）。
- OpenAPI JSON：<http://127.0.0.1:8000/openapi.json>。
- 健康检查：<http://127.0.0.1:8000/api/health>。
- 活动广场：<http://127.0.0.1:8000/>。
- 管理后台：<http://127.0.0.1:8000/admin>（仅本机访问）。
- 活动详情：`/activities/{id}`，从活动卡片进入。

启动生命周期自动创建 `data/campus.sqlite3` 和缺失的表，重复启动保留数据。默认路径基于项目位置，不依赖启动时的工作目录；可使用 `CAMPUS_DB_PATH` 指定其他文件路径。测试注入临时文件路径，绝不清空演示数据库。当前使用文件数据库，不支持 `:memory:` 多连接模式。

## API

| 方法 | 路径 | 用途 | 成功状态 |
|---|---|---|---|
| GET | `/api/health` | 检查应用与数据库可读性 | 200 |
| GET | `/api/categories` | 返回固定分类 | 200 |
| GET | `/api/activities` | 列表、搜索、分类筛选、分页 | 200 |
| GET | `/api/activities/{id}` | 详情、报名数、剩余名额、报名状态 | 200 |
| POST | `/api/activities/{id}/registrations` | 提交报名 | 201 |
| GET | `/api/admin/activities` | 管理活动列表，支持相同筛选参数 | 200 |
| POST | `/api/admin/activities` | 创建活动 | 201 |
| PUT | `/api/admin/activities/{id}` | 完整更新活动的全部业务字段 | 200 |
| DELETE | `/api/admin/activities/{id}` | 删除活动并级联删除报名 | 204（无响应体） |
| GET | `/api/admin/activities/{id}/registrations` | 分页读取报名名单 | 200 |
| GET | `/api/admin/stats` | 活动数、报名人次、去重学生数和各活动人数 | 200 |

列表参数：`q`（最多 100 字符）、`category`、`page`（默认 1，范围 1–1000000）、`page_size`（默认 20，范围 1–100）。关键词匹配标题、社团、介绍，可与分类组合使用，`%`、`_` 按普通字符匹配。活动按开始时间和 ID 升序排列，名单按报名 ID 升序排列。

列表和名单响应为 `{ "items": [...], "total": 0, "page": 1, "page_size": 20 }`。超出末页返回空 `items`，保留真实 `total`。

### 活动输入

创建和 PUT 使用相同完整 JSON。以下日期为格式示例；实际报名演示请填写未来时间：

```json
{
  "title": "校园摄影分享会",
  "club_name": "摄影社",
  "category": "文艺体育",
  "location": "学生活动中心 201",
  "description": "交流校园摄影经验，欢迎同学参加。",
  "capacity": 30,
  "starts_at": "2030-05-10T14:00:00+08:00",
  "ends_at": "2030-05-10T16:00:00+08:00",
  "registration_deadline": "2030-05-09T18:00:00+08:00"
}
```

- 必填字符串去除首尾空白，不得为空。标题、社团最多 100 字符，地点最多 200，介绍最多 5000。
- 文本禁止包含 NUL 空字符；时间转为 UTC 后必须仍在支持范围内，非法输入返回 422。
- 分类固定为：学术科技、文艺体育、志愿公益、实践交流、其他。
- 容量必须是 JSON 整数，范围 1–100000；不接受布尔值、浮点数或数字字符串。
- 时间必须带时区，结束晚于开始，截止不晚于开始；统一转为 UTC 保存和返回。数据库使用固定微秒精度的时间文本。
- 允许录入历史活动，但历史/截止活动无法报名。截止时间相等的瞬间也视为已关闭。
- PUT 需要提交全部业务字段，不接受局部更新及额外字段；容量不能降到已报名人数以下。
- 活动输出还包含 `id`、`created_at`、`updated_at`、`registration_count`、`remaining_capacity` 和 `registration_status`。报名状态为 `open`、`full` 或 `closed`，关闭状态优先于满员状态。

### 报名输入

```json
{
  "name": "张同学",
  "student_id": "20260001",
  "contact": "student@example.com"
}
```

姓名 1–50 字符，学号 1–32 字符（仅英文字母、数字、下划线、连字符），联系方式 1–100 字符。联系方式允许填写邮箱、电话或其他联系文本，不强制绑定某一种格式。所有字段必填并去除首尾空白，学号统一转为大写，同一学号不能重复报名同一活动，可以报名不同活动。

报名成功返回本人报名记录（ID、活动 ID、姓名、学号、联系方式、时间）。公开活动查询只返回汇总人数，不返回名单及联系方式。管理名单和报名回执使用 `Cache-Control: no-store`。

### 错误处理

```json
{
  "error": {
    "code": "ACTIVITY_FULL",
    "message": "活动报名名额已满。",
    "details": []
  }
}
```

| 状态 | 常见错误代码及含义 |
|---|---|
| 403 | `ADMIN_LOCAL_ONLY`、`UNTRUSTED_HOST`、`UNTRUSTED_ORIGIN`：访问限制 |
| 404 | `ACTIVITY_NOT_FOUND`：活动不存在；`NOT_FOUND`：路由不存在 |
| 405 | `METHOD_NOT_ALLOWED`：不支持此方法 |
| 409 | `ALREADY_REGISTERED`：重复报名；`ACTIVITY_FULL`：满员；`REGISTRATION_CLOSED`：截止/已开始；`CAPACITY_BELOW_REGISTRATIONS`：容量不足 |
| 422 | `VALIDATION_ERROR`：字段、JSON、路径或查询参数不合法；details 给出字段位置及原因 |
| 503 | `DATABASE_UNAVAILABLE`：数据库操作暂时不可用，带 `Retry-After: 1` |
| 500 | `DATABASE_ERROR`：数据库约束等内部操作失败，不返回 SQL 或内部路径 |

同一报名同时触发多个冲突时，按“活动存在 → 重复报名 → 时间关闭 → 容量满员”的顺序判断。字段验证先于业务处理。

活动 ID 必须在 1–9223372036854775807（SQLite 有符号整数范围）之内；超出范围返回 422，合法范围内不存在的 ID 返回 404。

### 统计口径

`activity_count` 是当前活动数量，`registration_count` 是报名人次，`unique_student_count` 是所有活动中按规范化学号去重后的学生数。`activities` 包含各活动的容量、报名数和剩余名额。删除活动后，其报名不再计入任何统计。

## 数据库与并发

- `activities` 保存活动内容和时间；`registrations` 保存报名，外键使用 `ON DELETE CASCADE`。
- 每次连接都启用 `PRAGMA foreign_keys=ON`；设置唯一约束 `UNIQUE(activity_id, student_id)` 及容量、必填、时间关系检查。
- 分类/时间查询有索引；报名唯一索引同时支持按活动统计和查重。
- 报名和活动修改、删除使用 `BEGIN IMMEDIATE`。容量检查和写入在同一事务完成，失败回滚，避免最后名额超额或容量修改与报名竞争。
- 每个业务调用使用独立连接并及时关闭。统计与分页使用读事务，保证总数与明细来自同一快照。
- 当前初始化只负责创建缺失表，不包含旧版本表结构自动迁移，也不会覆盖已有数据。

## 本地管理边界

这是无需登录的**本地考核演示程序**，不区分同一台计算机上的不同操作者。

- 必须按启动命令绑定 `127.0.0.1`，保留 `--no-proxy-headers`，不要绑定 `0.0.0.0` 或 `::`。
- 所有请求的 Host 限制为 localhost、127.0.0.1、[::1]；管理请求额外要求真实连接来源为回环地址，拒绝常见转发头。
- API 写操作拒绝非同源 Origin 和浏览器跨站请求，不启用 CORS。无 Origin 的本机 CLI 请求允许操作。
- 禁止通过反向代理、端口转发、内网穿透或公网部署暴露本服务；去掉代理头会破坏管理接口的来源边界。未来公网部署必须先增加真正的身份认证及授权。
- 管理静态 HTML 的大小写、点路径等替代写法也受本机访问限制；页面禁止被其他网站嵌入，避免点击劫持。
- DELETE 会永久删除活动及关联报名；前端已经提供显示关联报名人数的确认框，直接 API 调用即执行删除。
- SQLite 包含个人信息，数据库目录已加入 `.gitignore`；不要提交、发布或放入静态目录。

## 前端页面与静态文件

`app/main.py` 将 `app/static/` 挂载到 `/static`，仅该目录内资源可访问，不暴露项目根目录及数据库。`/`、`/activities/{id}` 和 `/admin` 分别返回活动广场、详情报名页和管理后台。管理页面及 `/static/admin.html` 同样限制本机访问。

前端使用原生 ES modules，无打包工具、大型框架或外部字体、图片依赖，与后端同源提供，无需另外启动前端服务。请通过 HTTP 地址访问，不要双击 HTML 使用 `file://` 打开。

公开页面与静态资源返回 `Cache-Control: no-cache`，管理页面和名单使用 `no-store`。入口资源和公共 UI 模块带发布版本标记，避免浏览器继续复用旧脚本。

- `api.js`：统一网络请求、15 秒超时、后端错误、主动取消过期请求。写入连接中断时会提醒先确认结果，避免盲目重复提交。
- `ui.js`：统一图标、北京时间、分页、成功通知、空数据/加载/失败状态和表单字段错误。
- `activities.js`：搜索、分类筛选、分页和活动卡片；筛选条件保留在 URL。
- `activity.js`：详情、报名、名额刷新、重复/满员/截止提示、报名成功及过期页面处理。
- `admin.js`：真实统计、活动 CRUD、编辑回填、名单分页和删除确认；提交期间禁用相关按钮。
- CSS 使用统一颜色与间距变量，桌面卡片三列、平板两列、手机单列；手机管理列表改为分块行，编辑表单改为单列，名单可横向滚动。
- API 文本先转义或通过 `textContent` 输出；不将表单个人信息写入 localStorage。
- 前端展示和编辑时间均按北京时间（UTC+8），不受浏览器所在时区影响，提交时转为带时区的 ISO 时间。

### 本地体验顺序

1. 启动服务，打开管理后台，点击「创建活动」，填写未来时间及其他必填字段。
2. 返回活动广场，使用关键词、分类筛选，打开卡片详情并填写报名。
3. 回到后台查看统计、报名名单；编辑活动并确认详情同步更新。
4. 点击删除，确认框会显示当前报名数量；确认后活动和关联报名一起删除。

加载中、空结果、服务不可用和操作成功均有页面提示。后端 422 字段校验错误会展示中文摘要及对应字段提示，失败后保留输入。名额已满或截止时禁用报名，错误后的重试不会用虚构数据填补。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/smoke_test.py
.\.venv\Scripts\python.exe -m pip check
```

pytest 使用 FastAPI TestClient 的上下文管理器执行应用生命周期。每项测试独立临时数据库，覆盖 CRUD、搜索/筛选/分页、输入和时间校验、缺失活动、重复/满员/截止、名单隐私、容量修改、外键/唯一约束、级联删除、重启持久化、统计、静态文件隔离、本机/Host/Origin 限制、数据库异常，以及并发抢名额、并发重复报名、容量缩减与报名竞争。

新增页面交付测试覆盖 HTML、模块脚本、CSS、图标资源以及管理页面的本机访问与缓存限制。前后端联调使用独立临时 SQLite，通过内置浏览器实际操作创建、搜索、筛选、报名、重复报名、满员、名单、编辑、删除及服务中断后的重试恢复。测试记录不会自动导入默认数据库。

2026-10-27 交付前审查：在未复制原虚拟环境和数据库的副本中重新创建虚拟环境、安装依赖、执行 README 启动命令，自动建库成功。完整回归实际结果为 `109 passed in 7.51s`，无失败、无警告；真实 Uvicorn HTTP 验证和 `pip check` 通过。原有 91 项测试及断言全部保留，新增 18 项交付回归覆盖边界输入、安全限制、首次建库及整个服务进程重启后的数据持久化。

本轮还通过内置浏览器验证了创建活动后首页显示、报名刷新保留、重复拒绝、满员禁用、名单、编辑、容量缩减冲突、级联删除及删除后的 404，控制台无未处理异常，服务日志未发现 500。浏览器检查包含桌面与 390×844 手机尺寸；未进行 Safari/Firefox 实机验证。详细记录见 `TEST_REPORT.md`。

如果受限执行环境的系统临时目录不可写，pytest 会在 `tmp_path` 初始化时失败。可改用虚拟环境内的**全新随机目录**，不需要修改或跳过测试：

```powershell
$testTemp = Join-Path (Resolve-Path .venv) ("pytest-" + [guid]::NewGuid().ToString("N"))
.\.venv\Scripts\python.exe -m pytest -q --basetemp $testTemp
```

`--basetemp` 会清理指定目录，因此不要将它设置为现有项目、`data/` 或任何重要目录。

`pytest.ini` 关闭非必要的结果缓存，避免受限目录中的缓存权限警告。测试断言不依赖请求的先后调度顺序。

smoke 脚本另启真实 Uvicorn 子进程，使用随机本地端口和临时数据库，通过真实 HTTP 验证健康检查、创建、报名、重复拦截、名单、统计、删除及级联结果，完成后关闭进程并清理临时数据库。

## 代码结构

```text
app/main.py           应用工厂、生命周期、路由与静态挂载
app/db.py             SQLite 初始化、连接和事务
app/schemas.py        Pydantic 输入输出模型
app/services.py       活动、报名、统计业务规则
app/security.py       本地管理、Host 和写入来源限制
app/errors.py         统一错误响应
app/routers/          公开接口与本地管理接口
app/static/*.html     活动广场、详情报名、管理页面
app/static/css/       统一样式与响应式布局
app/static/js/        API 封装、通用 UI 和各页面逻辑
tests/                接口、约束、并发测试
scripts/smoke_test.py  真实服务 HTTP 验证
```

事务和生命周期实现参考 [Python sqlite3 文档](https://docs.python.org/3.13/library/sqlite3.html)、[FastAPI 生命周期测试文档](https://fastapi.tiangolo.com/advanced/testing-events/)。

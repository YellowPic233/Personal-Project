# 后端验证记录

日期：2026-10-27（Asia/Shanghai）

环境：Windows、Python 3.13.14，依赖版本见 requirements.txt / requirements-dev.txt。

## 实际执行结果

| 命令 | 结果 |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest tests/test_database.py tests/test_activities.py -q` | 第一轮 36 passed；发现 TestClient 弃用及缓存权限警告 |
| `.\.venv\Scripts\python.exe -m pytest -q` | 补齐业务测试后 79 passed，0 警告 |
| `.\.venv\Scripts\python.exe -m pytest -q` | 最终 83 passed in 3.94s，0 失败、0 警告 |
| `.\.venv\Scripts\python.exe scripts/smoke_test.py` | PASS：真实 Uvicorn HTTP 健康检查、创建、报名、重复拦截、名单、统计、删除与级联结果 |
| `.\.venv\Scripts\python.exe -m pip check` | No broken requirements found. |

## 处理记录

- Starlette 1.10.0 对旧 httpx TestClient 后端发出弃用提示：改用其支持的 httpx2，并固定测试依赖版本。
- 受限目录下 pytest 创建缓存收到权限警告：关闭不影响测试执行的 cacheprovider，不隐藏警告。
- 检查中强化了畸形 Host 的处理：从 ASGI scope 读取 scheme/path，畸形 IPv6 和无效端口返回统一 403。
- 没有通过跳过测试、放宽业务规则或禁用访问限制来取得通过结果。

## 覆盖与边界

- 覆盖公开及管理接口的正常流程、输入错误和业务冲突。
- 六线程同时抢最后一个名额，仅一个 201，其余 409；六线程同学号报名，仅产生一条记录。
- 同时缩减容量和提交报名，无论调度先后都满足报名人数不超过容量。
- 验证 SQLite 外键、唯一约束、容量/时间 CHECK、事务回滚、级联删除、重启持久化。
- 验证管理请求本机限制、代理头、Host、Origin、公开响应隐私及静态资源目录隔离。
- 所有测试和真实服务验证均使用临时数据库；没有向默认演示数据库添加测试数据。

目前没有已知的未解决后端功能错误。前端尚未开发；本地管理无需登录，不能用于公网部署；已有数据库结构升级尚无自动迁移机制。以上为当前交付范围和运行边界。

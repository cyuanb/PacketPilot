# 配置与运行

真实配置放在忽略的 .env 或进程环境中，不提交到 Git。

| 字段 | 用途 |
| --- | --- |
| DATABASE_URL | 独立 PostgreSQL 应用数据库的 SQLAlchemy URL |
| LLM_BASE_URL | 可访问的兼容接口地址，通常包含 /v1 |
| LLM_API_KEY | 模型服务密钥 |
| LLM_MODEL | 支持工具调用的模型名称 |
| OWNER_USERNAME | 首次创建的本地账号 |
| OWNER_PASSWORD | 首次登录密码，至少 10 位 |
| APP_ORIGIN | 实际浏览器入口，默认 http://localhost:8010 |
| DATA_DIR | 私有文件目录 |
| COOKIE_SECURE | HTTPS 部署时启用安全 Cookie |

数据库密码中的特殊字符应做 URL 编码。初始化不会修改现有数据库角色，也不重置已经创建的用户密码。

Node 使用 .nvmrc 的锁定版本和 PacketPilot 别名。PACKETPILOT_NPM_CACHE 可以指定 npm 缓存位置。

API 与 Worker 必须同时运行。开发模式下 Vite 默认使用 5173，并代理到 8010；更换端口时同步调整应用入口和代理配置。

API 文档位于 /api/docs。运行日志位于 data/runtime；日志不是需要提交的项目文件。

连接失败时分别检查数据库端口、模型可达性、Worker 状态和对应日志。不要将完整凭据或原件粘贴到公共问题反馈中。

## 更新已有安装

更新代码前备份应用数据库与私有文件。停止 API 和 Worker 后，运行数据库迁移并重新构建前端，再启动服务：

~~~powershell
.\scripts\stop.ps1
git pull --ff-only
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
nvm use PacketPilot
npm ci --prefix frontend
npm run build --prefix frontend
.\scripts\start.ps1
~~~

工作空间迁移会按原所有者回填已有事项，不创建推测的申请人档案。已有主体或修改过的工作空间信息时，直接降级会被拒绝，避免静默丢失新增数据；需要回退时应使用迁移前的数据库与文件备份。

资料中心迁移保留原件位置、哈希及旧检查记录，并为旧材料回填独立资料版本，不移动或改写文件。存在资料数据时会拒绝直接降级。若旧记录对同一原件保存了互相矛盾的哈希或大小，迁移会中止并回滚，应先核对原始记录；不会猜测应保留哪份内容。

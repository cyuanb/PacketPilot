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

# 测试

安装依赖并配置可用 PostgreSQL 后运行：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
~~~

检查包括源码凭据与公开内容检查、Python 静态检查、pytest、前端状态测试与前端构建。数据库集成测试使用独立随机测试 Schema，账号需要相应权限；不会清空应用表。

HTTP 契约测试将完整 OpenAPI 定义与 `backend/tests/fixtures/api-contract.json` 比对，并验证登录会话、静态页面与 API 共存、SSE 游标续传及跨批次事件读取。接口有意变化时，应审查契约差异后更新该文件；不要只为消除测试失败而重新生成。

前端状态测试使用 Node 内置测试运行器，可在 `frontend` 目录运行 `npm test`。测试覆盖 URL 兼容、缓存按事项隔离、请求去重、过期成功/失败响应、修改后的刷新、退出时清理以及任务订阅和轮询释放；不需要模型服务。

浏览器验收还应覆盖：刷新与前进后退、旧链接、快速切换事项、弹窗失败后的草稿与重试、材料证据预览，以及窄屏下的标签页和表单。使用合成资料；网络模拟可以验证延迟与失败交互，但不能代替后端集成测试和真实部署验证。

需要实际模型的流程测试是显式可选操作：

~~~powershell
.\.venv\Scripts\python.exe scripts/live_check.py
~~~

它要求本机 API 和 Worker 正在运行，使用合成资料并消耗模型额度。输出保存在忽略的本地产物目录，不作为产品说明提交。

测试不能替代对所有真实材料的质量验证。新增规则应包括错误、未知、版本变化和错误通过等反例。

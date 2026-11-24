# 测试

安装依赖并配置可用 PostgreSQL 后运行：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
~~~

检查包括源码凭据检查、Python 静态检查、pytest 与前端构建。数据库集成测试使用独立随机测试 Schema，账号需要相应权限；不会清空应用表。

需要实际模型的流程测试是显式可选操作：

~~~powershell
.\.venv\Scripts\python.exe scripts/live_check.py
~~~

它要求本机 API 和 Worker 正在运行，使用合成资料并消耗模型额度。输出保存在忽略的本地产物目录，不作为产品说明提交。

测试不能替代对所有真实材料的质量验证。新增规则应包括错误、未知、版本变化和错误通过等反例。

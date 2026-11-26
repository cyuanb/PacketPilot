# 齐备 · PacketPilot

有依据的材料预检，有条理的申请准备。

PacketPilot 是可自行部署的开源材料准备工作台，将通知、资料、检查结果和补件对话组织在一起。

[English](README.en.md) · [使用说明](docs/usage.md) · [配置说明](docs/configuration.md) · [架构](docs/architecture.md) · [测试](docs/testing.md)

当前版本：0.1.1。软件使用 Apache-2.0 许可；自行配置的模型或基础设施可能产生资源费用。

## 功能

- 创建和管理材料事项，保存通知与材料版本。
- 管理工作空间内的个人／组织主体档案，为事项明确关联申请主体、推荐人、经办人等角色。同名档案分别保存，关联变动会提示重新核对。
- 提取带原文引用的要求草稿，审阅后启用。
- 读取 PDF、DOCX、TXT、Markdown；保存图片并支持人工校订文本。
- 执行明确字段、格式、页数、日期和内容检查，查看引用与待处理问题。
- 通过工具调用助手进行多轮分析、追问和补件复检。
- 记录人工确认，导出 HTML 或 Markdown 检查清单。
- 检查会验证逐材料字段覆盖、当前要求集合和引擎版本。历史或不完整结果需要重新预检，不能作为当前完整结果导出。

## 快速开始

需要 Git、nvm for Windows、.nvmrc 指定的 Node、Python 3.11+ 和 PostgreSQL。数据库和模型地址通过本地配置提供。

~~~powershell
git clone https://github.com/cyuanb/PacketPilot.git
cd PacketPilot
Copy-Item .env.example .env
~~~

填写 .env 的 DATABASE_URL、LLM_BASE_URL、LLM_API_KEY 和 LLM_MODEL，再运行：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
~~~

打开 http://localhost:8010。登录账号由 OWNER_USERNAME 配置，密码见本地 OWNER_PASSWORD。初始化时密码为空会生成随机密码，不存在通用默认登录密码。

停止应用：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/stop.ps1
~~~

脚本以原生进程运行，不依赖 Docker，不停止共享数据库服务。已有数据库用户可复用，但应使用单独的应用数据库。

## 使用流程

创建事项 → 导入通知 → 提取并启用要求 → 上传资料 → 预检与查看证据 → 补件复检 → 人工确认 → 导出清单。

“体验一个示例申请”使用虚构机构与合成资料，可以独立修改和删除。

## 当前限制

- 自动 OCR、通用文档分类、真实性鉴定和自动提交尚未提供。
- 规则检查针对明确可读取的内容；非标准版式、未知条件或识别不足应保留待确认状态。
- 原件保存在本机，必要文本片段会发送到配置的模型服务；不是默认完全离线应用。
- 适合本地单所有者使用。对外部署需要独立验证权限、网络与运行条件。
- 检查清单帮助准备材料，不保证机构受理或其他审批结果。

## 贡献与许可

见 [CONTRIBUTING](CONTRIBUTING.md)、[SECURITY](SECURITY.md) 和 [LICENSE](LICENSE)。请使用合成资料报告问题，不上传私人文档或凭据。

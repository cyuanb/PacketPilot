# Changelog

## 0.9.0

- Add persistent work plans, questions, drafts, deadline reminders and calendar export.
- Add immutable PDF/image derivatives and provenance.
- Add scoped invitations, collection submissions, version-bound reviews, session revocation and single-use recovery codes.
- Add portable data backup/restore, reference-aware permanent deletion, diagnostics and controlled retries.
- Keep the release in preview pending real-user and declared-scenario acceptance.


## 0.6.0

- Freeze selected material files into verifiable packets and record delivery/acknowledgement history separately from downloads.
- Add native CPU OCR, append-only parse revisions, page previews, region locations and field/page corrections.
- Add explicit material subject/slot assignments, requirement trees, independent quantities, translation pairs and date windows.
- Add visual rule editing, dry runs, source-conflict handling, expiry and explicit scenario updates.
- Expand starter scenarios to research funding, competitions, credential renewal and volunteer applications.


## 0.3.0

- 为事项选择资料中心的固定版本，提示新版本并由用户显式切换；不同事项独立更新，解除引用保留原件。
- 增加教育交流、求职、入职、企业入驻和供应商资料的起步配置，区分个人/组织主体、背景字段和材料建议；实际要求仍需引用接收方通知。
- 增加基于原文引用的简单要求表单和不调用模型的基础预检，语义项保持待确认。
- 增加问题与补件进展、处理记录、复检后解决/重开及本次检查例外；手动进展和例外不会伪装成检查通过。
- 当前仍不生成实际材料包，不提供正式行业认证或完整分主体字段判断。

## 0.2.0

- 增加所有者工作空间、独立个人/组织主体档案与事项角色关联。
- 增加资料中心和未指定主体的收集箱，可独立上传、分类、搜索、归档与查看使用位置。
- 原件和资料版本独立保存；相同文件提示重复，但仍保存用户提交的新资料或新版本。
- 旧材料回填资料中心，原件哈希、事项版本和检查记录保持；资料中心更新不会自动替换事项材料。
- 从事项移除材料或删除事项后，资料中心继续保留原件。资料中心当前提供归档，不提供永久清除原件的入口。
- 支持页面深链接、前进后退、请求状态隔离和错误恢复。

## 0.1.1

- 分别核对每份材料的字段和日期，避免重复值覆盖其他材料的缺失。
- 区分材料提及与有限结构确认，保留无法确认的情况。
- 完整性、引擎版本和输入新鲜度共同决定结果是否可使用。
- 展示字段覆盖与候选依据，旧结果需要重新检查。

## 0.1.0

提供通知、材料版本、要求审阅、工具调用助手、补件复检、历史和清单导出。

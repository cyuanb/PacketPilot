"""Starter workflow configurations, not institution-specific or official requirements."""

from copy import deepcopy

from fastapi import HTTPException

SCENARIOS = [
    {
        "id": "education_exchange",
        "kind": "exchange",
        "family": "education",
        "title": "教育申请与交流",
        "description": "按项目整理申请人与推荐人材料，复用同一资料时保留各事项版本。",
        "primary_subject_kind": "person",
        "roles": [
            {"role": "applicant", "label": "申请人"},
            {"role": "recommender", "label": "推荐人"},
            {"role": "organization", "label": "接收院校"},
        ],
        "facts": ["申请类别", "目标项目", "申请学年"],
        "materials": ["申请表", "成绩单", "学习计划", "推荐信"],
        "stages": ["确认项目通知", "整理申请与推荐材料", "处理缺件和人工核对"],
    },
    {
        "id": "job_application",
        "kind": "job_application",
        "family": "employment",
        "title": "求职与实习材料",
        "description": "针对不同岗位分别准备简历、作品与证明，不把其他岗位的资料版本自动套入。",
        "primary_subject_kind": "person",
        "roles": [
            {"role": "applicant", "label": "求职者"},
            {"role": "organization", "label": "接收单位"},
            {"role": "contact", "label": "联系人员"},
        ],
        "facts": ["目标岗位", "申请批次", "作品提交方式"],
        "materials": ["简历", "作品集", "学历证明", "资格证明"],
        "stages": ["确认岗位材料要求", "选择岗位版本", "核对事实和附件"],
    },
    {
        "id": "onboarding",
        "kind": "onboarding",
        "family": "employment",
        "title": "入职资料准备",
        "description": "区分员工、单位与经办人，按入职阶段收集资料并跟踪补件。",
        "primary_subject_kind": "person",
        "roles": [
            {"role": "applicant", "label": "入职员工"},
            {"role": "organization", "label": "用人单位"},
            {"role": "representative", "label": "经办人"},
        ],
        "facts": ["入职日期", "岗位", "资料准备阶段"],
        "materials": ["入职登记表", "学历证明", "资格证明", "签署文件"],
        "stages": ["确认单位清单", "整理员工与单位资料", "处理签署和补件"],
    },
    {
        "id": "business_entry",
        "kind": "business_entry",
        "family": "business",
        "title": "企业入驻与资质资料",
        "description": "以组织作为申请主体，分清经办人和授权文件，按具体接收方要求准备。",
        "primary_subject_kind": "organization",
        "roles": [
            {"role": "applicant", "label": "申请企业"},
            {"role": "representative", "label": "经办人"},
            {"role": "organization", "label": "接收组织"},
        ],
        "facts": ["入驻平台或接收方", "业务范围", "办理事项"],
        "materials": ["营业执照", "授权书", "资质证书", "业务资料"],
        "stages": ["确认接收方要求", "核对组织与经办角色", "准备证照和授权"],
    },
    {
        "id": "supplier_qualification",
        "kind": "supplier",
        "family": "business",
        "title": "供应商准入与更新",
        "description": "同一企业面向不同客户的要求分别维护，资料更新只影响明确接受新版的事项。",
        "primary_subject_kind": "organization",
        "roles": [
            {"role": "applicant", "label": "供应商企业"},
            {"role": "organization", "label": "客户或采购方"},
            {"role": "representative", "label": "经办人"},
        ],
        "facts": ["客户名称", "供货类别", "准入或更新阶段"],
        "materials": ["营业执照", "资质证书", "授权书", "供应商问卷"],
        "stages": ["确认客户专属清单", "选择证照和问卷版本", "跟踪有效期与补件"],
    },
]


SCENARIOS.extend(
    [
        {
            "id": "research_grant",
            "kind": "research_grant",
            "family": "research",
            "title": "科研与资助申报",
            "description": "按资助通知整理负责人、依托单位、申报书与合作证明，保留提交批次。",
            "primary_subject_kind": "person",
            "roles": [
                {"role": "applicant", "label": "项目负责人"},
                {"role": "organization", "label": "依托单位"},
                {"role": "contact", "label": "项目联系人"},
            ],
            "facts": ["资助项目", "申报年度", "项目类别"],
            "materials": ["申报书", "研究计划", "预算说明", "合作证明"],
            "stages": ["确认申报通知与适用条件", "核对负责人及依托单位", "准备研究与预算材料"],
        },
        {
            "id": "competition_submission",
            "kind": "competition",
            "family": "creative",
            "title": "竞赛与作品征集",
            "description": "区分报名材料和参赛作品，核对组别、提交格式、授权和交付版本。",
            "primary_subject_kind": "person",
            "roles": [
                {"role": "applicant", "label": "参赛人"},
                {"role": "organization", "label": "主办方"},
                {"role": "representative", "label": "团队代表"},
            ],
            "facts": ["参赛组别", "作品类别", "是否团队参赛"],
            "materials": ["报名表", "作品说明", "作品集", "授权书"],
            "stages": ["确认征集规则与组别", "核对作品和授权范围", "固定本次提交版本"],
        },
        {
            "id": "credential_renewal",
            "kind": "credential",
            "family": "professional",
            "title": "资格与证照续期",
            "description": "按指定机构通知核对持证人、有效期间和继续教育证明；不判断法定执业资格。",
            "primary_subject_kind": "person",
            "roles": [
                {"role": "applicant", "label": "持证人"},
                {"role": "organization", "label": "接收机构"},
            ],
            "facts": ["资格名称", "续期周期", "受理机构"],
            "materials": ["续期申请表", "资格证明", "继续教育证明"],
            "stages": ["确认本次续期通知", "核对有效期间和证明数量", "整理续期材料"],
        },
        {
            "id": "volunteer_application",
            "kind": "volunteer",
            "family": "community",
            "title": "公益与志愿报名",
            "description": "按具体活动清单整理报名、培训和授权材料，保留补件与接收记录。",
            "primary_subject_kind": "person",
            "roles": [
                {"role": "applicant", "label": "报名人"},
                {"role": "organization", "label": "活动组织方"},
                {"role": "contact", "label": "联系人"},
            ],
            "facts": ["活动名称", "报名岗位", "活动期间"],
            "materials": ["报名表", "培训证明", "授权书"],
            "stages": ["确认活动和岗位要求", "整理报名与培训材料", "核对授权并准备交付"],
        },
    ]
)


def catalog():
    return [
        {
            **deepcopy(item),
            "version": "2",
            "slots": [
                {"id": f"material-{i}", "label": name, "document_type": name}
                for i, name in enumerate(item["materials"], 1)
            ],
            "output": {
                "folder": item["id"],
                "naming": "序号_材料名称_版本.原扩展名",
                "notice": "这是可编辑的整理建议；以接收方通知为准，不自动强制格式或数量",
            },
            "support_level": "starter",
            "notice": "通用起步配置，不是官方材料清单；检查要求须引用你提供的接收方通知。",
        }
        for item in SCENARIOS
    ]


def scenario_snapshot(identifier):
    if not identifier:
        return {}
    item = next((item for item in catalog() if item["id"] == identifier), None)
    if item is None:
        raise HTTPException(422, "场景配置不存在")
    return item

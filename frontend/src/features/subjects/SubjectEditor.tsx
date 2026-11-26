import { useState } from "react";
import { api } from "../../api/client";
import { useAsyncAction } from "../../app/useAsyncAction";
import { Dialog } from "../../components/Dialog";
import { attributeLabels, kindLabels } from "./labels";
import type { Subject, SubjectKind } from "./types";

export function SubjectEditor({
  subject,
  close,
  saved,
}: {
  subject: Subject | null;
  close: () => void;
  saved: () => void;
}) {
  const [kind, setKind] = useState<SubjectKind>(subject?.kind || "person");
  const [name, setName] = useState(subject?.name || "");
  const [label, setLabel] = useState(subject?.label || "");
  const [attributes, setAttributes] = useState<Record<string, string>>({
    ...subject?.attributes,
  });
  const { act, error, busy } = useAsyncAction();
  return (
    <Dialog
      title={subject ? "编辑主体档案" : "新建主体档案"}
      close={close}
      error={error}
      busy={busy}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          act(async () => {
            await api(subject ? "/subjects/" + subject.id : "/subjects", {
              method: subject ? "PATCH" : "POST",
              body: JSON.stringify({
                kind,
                name,
                label,
                attributes,
                ...(subject
                  ? { revision: subject.revision, archived: subject.archived }
                  : {}),
              }),
            });
            saved();
          });
        }}
      >
        <p className="dialog-intro">
          为每个人或组织分别建档。同名档案不会自动合并；修改关联中的档案会提示事项重新核对。
        </p>
        <label>
          主体类型
          <select
            value={kind}
            disabled={!!subject || busy}
            onChange={(e) => {
              setKind(e.target.value as SubjectKind);
              setAttributes({});
            }}
          >
            {Object.entries(kindLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          {kind === "person" ? "姓名" : "组织名称"}
          <input
            required
            maxLength={200}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          区分备注
          <input
            maxLength={200}
            placeholder="例如：同名的导师、申请人或分支机构"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
        </label>
        {Object.entries(attributeLabels[kind]).map(([key, label]) => (
          <label key={key}>
            {label}
            <input
              maxLength={300}
              value={attributes[key] || ""}
              onChange={(e) =>
                setAttributes({ ...attributes, [key]: e.target.value })
              }
            />
          </label>
        ))}
        <div className="dialog-actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={close}
          >
            取消
          </button>
          <button className="primary" disabled={busy || !name.trim()}>
            {busy ? "正在保存…" : "保存档案"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

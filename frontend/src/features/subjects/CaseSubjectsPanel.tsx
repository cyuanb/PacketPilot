import { Plus, Trash2, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { Case } from "../../api/types";
import { useAsyncAction } from "../../app/useAsyncAction";
import { Dialog } from "../../components/Dialog";
import { allowsRole, kindLabels, roleLabels, subjectCaption } from "./labels";
import type { SubjectKind, SubjectList, SubjectRole } from "./types";

type Choice = {
  id: string;
  name: string;
  kind: SubjectKind;
  label: string;
  archived: boolean;
};
function RoleEditor({
  item,
  close,
  saved,
}: {
  item: Case;
  close: () => void;
  saved: () => Promise<void>;
}) {
  const scenarioLabels = Object.fromEntries(
    (item.scenario?.roles || []).map((role) => [role.role, role.label]),
  );
  const validRole = (kind: SubjectKind, role: SubjectRole) =>
    allowsRole(kind, role) &&
    (role !== "applicant" ||
      !item.scenario ||
      kind === item.scenario.primary_subject_kind);
  const [links, setLinks] = useState(
    (item.subjects || []).map((s) => ({
      subject_id: s.subject_id,
      role: s.role,
    })),
  );
  const [choices, setChoices] = useState<Record<string, Choice>>(() =>
    Object.fromEntries(
      (item.subjects || []).map((s) => [
        s.subject_id,
        { ...s, id: s.subject_id },
      ]),
    ),
  );
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [loadError, setLoadError] = useState("");
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [resultIds, setResultIds] = useState<string[]>([]);
  const { act, error, busy } = useAsyncAction();
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setResultIds([]);
    setLoadError("");
    api<SubjectList>("/subjects?limit=200&q=" + encodeURIComponent(search), {
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        setChoices((previous) => ({
          ...previous,
          ...Object.fromEntries(result.items.map((s) => [s.id, s])),
        }));
        setTotal(result.total);
        setResultIds(result.items.map((subject) => subject.id));
      })
      .catch((error) => {
        if (!controller.signal.aborted) setLoadError(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [search, attempt]);
  return (
    <Dialog
      title="关联主体与角色"
      close={close}
      error={error || loadError}
      busy={busy}
      wide
    >
      <p className="dialog-intro">
        按独立档案选择申请主体、推荐人或经办人。同名档案请核对区分备注和标识。保存后原检查结果需要复核。
      </p>
      <div className="subject-picker-search">
        <label>
          查找主体
          <input
            value={query}
            placeholder="输入名称或区分备注"
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <button
          className="secondary"
          disabled={loading}
          onClick={() => {
            setSearch(query);
            setAttempt((value) => value + 1);
          }}
        >
          查找
        </button>
      </div>
      {loading && <p role="status">正在读取主体…</p>}
      {total > 200 && <p>匹配超过 200 份，请输入更具体的名称或区分备注。</p>}
      {links.map((link, index) => (
        <div className="subject-link-row" key={index}>
          <label>
            主体 {index + 1}
            <select
              value={link.subject_id}
              onChange={(e) => {
                const id = e.target.value;
                setLinks(
                  links.map((value, i) =>
                    i === index
                      ? {
                          subject_id: id,
                          role:
                            choices[id] &&
                            validRole(choices[id].kind, value.role)
                              ? value.role
                              : "applicant",
                        }
                      : value,
                  ),
                );
              }}
            >
              <option value="">请选择一份档案</option>
              {Object.values(choices)
                .filter(
                  (subject) =>
                    resultIds.includes(subject.id) ||
                    links.some((link) => link.subject_id === subject.id),
                )
                .map((s) => (
                  <option
                    key={s.id}
                    value={s.id}
                    disabled={
                      (s.archived && s.id !== link.subject_id) ||
                      !validRole(s.kind, link.role)
                    }
                  >
                    {subjectCaption(s)}
                    {s.archived ? "（已归档）" : ""}
                  </option>
                ))}
            </select>
          </label>
          <label>
            角色 {index + 1}
            <select
              value={link.role}
              onChange={(e) =>
                setLinks(
                  links.map((value, i) =>
                    i === index
                      ? { ...value, role: e.target.value as SubjectRole }
                      : value,
                  ),
                )
              }
            >
              {Object.entries(roleLabels).map(([role, label]) => (
                <option
                  key={role}
                  value={role}
                  disabled={
                    !!choices[link.subject_id] &&
                    !validRole(
                      choices[link.subject_id].kind,
                      role as SubjectRole,
                    )
                  }
                >
                  {scenarioLabels[role] || label}
                </option>
              ))}
            </select>
          </label>
          <button
            className="icon-button"
            aria-label={"移除主体 " + (index + 1)}
            onClick={() => setLinks(links.filter((_, i) => i !== index))}
          >
            <Trash2 size={17} />
          </button>
        </div>
      ))}
      {!links.length && (
        <p>此事项尚未关联主体；不会把登录账号自动当作申请人。</p>
      )}
      <div className="subject-actions">
        <button
          className="secondary"
          disabled={links.length >= 50}
          onClick={() =>
            setLinks([...links, { subject_id: "", role: "applicant" }])
          }
        >
          <Plus size={16} />
          添加主体角色
        </button>
        <a className="text-action" href="#/subjects">
          管理主体档案
        </a>
      </div>
      <div className="dialog-actions">
        <button className="secondary" disabled={busy} onClick={close}>
          取消
        </button>
        <button
          className="primary"
          disabled={busy || links.some((link) => !link.subject_id)}
          onClick={() =>
            act(async () => {
              await api("/cases/" + item.id + "/subjects", {
                method: "PUT",
                body: JSON.stringify({ revision: item.revision, links }),
              });
              await saved();
              close();
            })
          }
        >
          保存关联
        </button>
      </div>
    </Dialog>
  );
}

export function CaseSubjectsPanel({
  item,
  onChanged,
}: {
  item: Case;
  onChanged: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  return (
    <section className="panel case-subjects">
      <div className="case-subjects-heading">
        <h2>
          <UsersRound size={18} />
          事项主体
        </h2>
        <button className="text-action" onClick={() => setEditing(true)}>
          关联主体与角色
        </button>
      </div>
      <p>档案记录涉及的人和组织；角色关联本身不代表已核验材料归属。</p>
      {item.subjects?.length ? (
        <ul className="case-subject-list">
          {item.subjects.map((s) => (
            <li key={s.subject_id + s.role}>
              <strong>
                {item.scenario?.roles.find((role) => role.role === s.role)
                  ?.label || roleLabels[s.role]}
              </strong>
              <span>
                {s.name} · {kindLabels[s.kind]}
                {s.label ? " · " + s.label : ""} · {s.subject_id.slice(0, 8)}
                {s.archived ? " · 已归档" : ""}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="hint">
          尚未指定申请主体或其他角色。<a href="#/subjects">先建立主体档案</a>
        </p>
      )}
      {editing && (
        <RoleEditor
          item={item}
          close={() => setEditing(false)}
          saved={onChanged}
        />
      )}
    </section>
  );
}

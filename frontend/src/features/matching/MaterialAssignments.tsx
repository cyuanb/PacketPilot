import { useEffect, useState } from "react";
import { api, type Case, type Doc } from "../../api";

type Assignment = {
  state: string;
  subject_id: string;
  document_type: string;
  slot_ids: string[];
  variant: string;
  pair_key: string;
  issuer: string;
};
type Candidate = {
  document_id: string;
  candidates: { document_type: string; status: string; reason: string }[];
};
const empty: Assignment = {
  state: "accepted",
  subject_id: "",
  document_type: "",
  slot_ids: [],
  variant: "original",
  pair_key: "",
  issuer: "",
};

function AssignmentForm({
  doc,
  item,
  candidates,
  refresh,
}: {
  doc: Doc;
  item: Case;
  candidates: Candidate["candidates"];
  refresh: () => Promise<void>;
}) {
  const [value, setValue] = useState<Assignment>({
    ...empty,
    ...doc.assignment,
    document_type: doc.assignment?.document_type || doc.category,
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(
    () =>
      setValue({
        ...empty,
        ...doc.assignment,
        document_type: doc.assignment?.document_type || doc.category,
      }),
    [doc.assignment, doc.category],
  );
  const slots = [...(item.scenario?.slots || [])];
  for (const r of item.rule_sets?.find((r) => r.status === "active")
    ?.requirements || []) {
    const id = r.parameters.slot_id;
    if (typeof id === "string" && id && !slots.some((s) => s.id === id))
      slots.push({ id, label: r.title, document_type: r.document_type });
  }
  return (
    <details className="assignment-card">
      <summary>
        {doc.title} ·{" "}
        {doc.assignment?.state === "accepted"
          ? "已确认归属"
          : doc.assignment?.state === "rejected"
            ? "已排除"
            : "待确认"}
      </summary>
      <p className="hint">
        类型候选与主体是不同信息。确认只适用于此材料版本；切换文件版本需重新确认。
      </p>
      {candidates.map((c) => (
        <p key={c.document_type}>
          {c.document_type}：{c.reason}
          <button
            onClick={() =>
              setValue({ ...value, document_type: c.document_type })
            }
          >
            采用类型
          </button>
        </p>
      ))}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            await api(`/documents/${doc.id}/assignment`, {
              method: "PUT",
              body: JSON.stringify({ ...value, revision: item.revision }),
            });
            await refresh();
          } catch (e) {
            setError(e instanceof Error ? e.message : "保存失败");
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="form-grid">
          <label>
            匹配决定
            <select
              value={value.state}
              onChange={(e) => setValue({ ...value, state: e.target.value })}
            >
              <option value="accepted">确认使用</option>
              <option value="rejected">排除此材料</option>
              <option value="unassigned">清除确认</option>
            </select>
          </label>
          <label>
            材料类型
            <input
              value={value.document_type}
              onChange={(e) =>
                setValue({ ...value, document_type: e.target.value })
              }
            />
          </label>
          <label>
            材料所属主体
            <select
              value={value.subject_id}
              onChange={(e) =>
                setValue({ ...value, subject_id: e.target.value })
              }
            >
              <option value="">尚未明确</option>
              {item.subjects
                ?.filter((s) => !s.archived)
                .map((s) => (
                  <option
                    key={`${s.subject_id}:${s.role}`}
                    value={s.subject_id}
                  >
                    {s.name} · {s.role}
                  </option>
                ))}
            </select>
          </label>
          <label>
            原件或译件
            <select
              value={value.variant}
              onChange={(e) => setValue({ ...value, variant: e.target.value })}
            >
              <option value="original">原件</option>
              <option value="translation">译件</option>
            </select>
          </label>
          <label>
            原件/译件配对标识
            <input
              placeholder="两份对应材料填写同一标识"
              value={value.pair_key}
              onChange={(e) => setValue({ ...value, pair_key: e.target.value })}
            />
          </label>
          <label>
            独立出具方
            <input
              placeholder="例如推荐人或出具机构，不能只填文件名"
              value={value.issuer}
              onChange={(e) => setValue({ ...value, issuer: e.target.value })}
            />
          </label>
        </div>
        <fieldset>
          <legend>材料槽位</legend>
          {slots.map((s) => (
            <label key={s.id}>
              <input
                type="checkbox"
                checked={value.slot_ids.includes(s.id)}
                onChange={(e) =>
                  setValue({
                    ...value,
                    slot_ids: e.target.checked
                      ? [...value.slot_ids, s.id]
                      : value.slot_ids.filter((v) => v !== s.id),
                  })
                }
              />
              {s.label}（{s.id}）
            </label>
          ))}
          {!slots.length && <p>可先在要求编辑器建立材料槽位。</p>}
        </fieldset>
        {error && <p role="alert">{error}</p>}
        <button disabled={busy}>保存匹配决定</button>
      </form>
    </details>
  );
}

export function MaterialAssignments({
  item,
  refresh,
}: {
  item: Case;
  refresh: () => Promise<void>;
}) {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    api<Candidate[]>(`/cases/${item.id}/material-candidates`)
      .then((v) => {
        if (live) setCandidates(v);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [item.id, item.revision]);
  return (
    <section className="panel assignments-panel">
      <h2>材料、主体与槽位</h2>
      <p className="hint">
        先明确哪份材料属于谁、用于哪个要求，再进行分主体检查。类型候选不会自动确认匹配。
      </p>
      {error && <p role="alert">{error}</p>}
      {item.documents
        ?.filter((d) => d.purpose === "material")
        .map((d) => (
          <AssignmentForm
            key={d.id}
            doc={d}
            item={item}
            candidates={
              candidates.find((c) => c.document_id === d.id)?.candidates || []
            }
            refresh={refresh}
          />
        ))}
    </section>
  );
}

import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { useAsyncAction } from "../../app/useAsyncAction";
import { Dialog } from "../../components/Dialog";
import { subjectCaption } from "../subjects/labels";
import type { Subject, SubjectList } from "../subjects/types";
import type { LibraryDetail } from "./types";

export function AssetEditor({
  asset,
  close,
  saved,
}: {
  asset: LibraryDetail;
  close: () => void;
  saved: (asset: LibraryDetail) => void;
}) {
  const [title, setTitle] = useState(asset.title),
    [category, setCategory] = useState(asset.category),
    [subject, setSubject] = useState(asset.subject_id || "");
  const [query, setQuery] = useState(""),
    [search, setSearch] = useState(""),
    [attempt, setAttempt] = useState(0);
  const [subjects, setSubjects] = useState<Subject[]>([]),
    [knownSubjects, setKnownSubjects] = useState<Record<string, Subject>>({}),
    [loadError, setLoadError] = useState("");
  const { act, busy, error, isCurrent } = useAsyncAction();
  useEffect(() => {
    const controller = new AbortController();
    setLoadError("");
    api<SubjectList>("/subjects?limit=200&q=" + encodeURIComponent(search), {
      signal: controller.signal,
    })
      .then((result) => {
        if (!controller.signal.aborted) {
          setSubjects(result.items);
          setKnownSubjects((previous) => ({
            ...previous,
            ...Object.fromEntries(
              result.items.map((subject) => [subject.id, subject]),
            ),
          }));
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) setLoadError(error.message);
      });
    return () => controller.abort();
  }, [search, attempt]);
  return (
    <Dialog
      title="整理资料"
      close={close}
      busy={busy}
      error={error || loadError}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          act(async () => {
            const result = await api<LibraryDetail>("/assets/" + asset.id, {
              method: "PATCH",
              body: JSON.stringify({
                revision: asset.revision,
                title,
                category,
                subject_id: subject || null,
                archived: asset.archived,
              }),
            });
            if (isCurrent()) saved(result);
          });
        }}
      >
        <p className="dialog-intro">
          确认资料属于谁，并填写便于查找的分类。整理资料不会改动原件或事项中的材料。
        </p>
        <label>
          资料名称
          <input
            required
            maxLength={250}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label>
          分类
          <input
            maxLength={100}
            placeholder="例如：身份证明、组织资质、申请通知"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          />
        </label>
        <div className="subject-picker-search">
          <label>
            查找主体
            <input
              maxLength={100}
              placeholder="按名称或区分备注查找"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setSearch(query);
              setAttempt((value) => value + 1);
            }}
          >
            查找
          </button>
        </div>
        <label>
          资料主体
          <select
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
          >
            <option value="">暂不指定，保留在收集箱</option>
            {subject && !subjects.some((s) => s.id === subject) && (
              <option value={subject}>
                {knownSubjects[subject]
                  ? subjectCaption(knownSubjects[subject])
                  : `${asset.subject_name} · ${asset.subject_label || "当前主体"}${asset.subject_archived ? "（已归档）" : ""}`}
              </option>
            )}
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {subjectCaption(s)}
              </option>
            ))}
          </select>
        </label>
        <a className="text-action" href="#/subjects">
          管理个人与组织档案
        </a>
        <div className="dialog-actions">
          <button
            type="button"
            disabled={busy}
            className="secondary"
            onClick={close}
          >
            取消
          </button>
          <button disabled={busy || !title.trim()} className="primary">
            保存整理信息
          </button>
        </div>
      </form>
    </Dialog>
  );
}

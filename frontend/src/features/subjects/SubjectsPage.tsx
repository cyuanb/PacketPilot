import { Building2, Plus, Search, UserRound, UsersRound } from "lucide-react";
import { useState } from "react";
import { api } from "../../api/client";
import type { QueryClient } from "../../app/queryClient";
import { useAsyncAction } from "../../app/useAsyncAction";
import { useResource } from "../../app/useResource";
import { Dialog } from "../../components/Dialog";
import { Empty } from "../../components/Empty";
import { attributeLabels, kindLabels, roleLabels } from "./labels";
import { SubjectEditor } from "./SubjectEditor";
import type {
  Subject,
  SubjectDetail,
  SubjectList,
  WorkspaceInfo,
} from "./types";

function WorkspaceName({
  workspace,
  saved,
}: {
  workspace: WorkspaceInfo;
  saved: () => void;
}) {
  const [name, setName] = useState(workspace.name);
  const { busy, error, act } = useAsyncAction();
  return (
    <form
      className="workspace-name-form"
      onSubmit={(e) => {
        e.preventDefault();
        act(async () => {
          await api("/workspace", {
            method: "PATCH",
            body: JSON.stringify({ name, revision: workspace.revision }),
          });
          saved();
        });
      }}
    >
      <label>
        工作空间名称
        <input
          maxLength={100}
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <button
        className="secondary"
        disabled={busy || !name.trim() || name === workspace.name}
      >
        保存名称
      </button>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
    </form>
  );
}

function SubjectUsage({
  id,
  client,
  close,
}: {
  id: string;
  client: QueryClient;
  close: () => void;
}) {
  const resource = useResource<SubjectDetail>(client, "/subjects/" + id);
  return (
    <Dialog
      title="主体与关联事项"
      close={close}
      error={resource.error?.message}
    >
      {!resource.data ? (
        <p>{resource.pending ? "正在读取…" : "未能读取档案"}</p>
      ) : (
        <>
          <h3>{resource.data.name}</h3>
          <p>
            {kindLabels[resource.data.kind]} ·{" "}
            {resource.data.label || "未填写区分备注"}
          </p>
          <p className="subject-id">档案标识：{resource.data.id}</p>
          <dl>
            {Object.entries(attributeLabels[resource.data.kind]).map(
              ([key, label]) => (
                <div key={key}>
                  <dt>{label}</dt>
                  <dd>{resource.data!.attributes[key] || "未填写"}</dd>
                </div>
              ),
            )}
          </dl>
          <h3>关联事项</h3>
          {resource.data.cases.length ? (
            <ul className="subject-usage">
              {resource.data.cases.map((link) => (
                <li key={link.id + link.role}>
                  <a href={"#/cases/" + link.id + "/overview"}>{link.title}</a>
                  <span>{roleLabels[link.role]}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>尚未关联事项，可在申请页面添加主体角色。</p>
          )}
        </>
      )}
      {resource.error && (
        <button
          className="secondary"
          onClick={() => resource.reload().catch(() => {})}
        >
          重试
        </button>
      )}
    </Dialog>
  );
}

export function SubjectsPage({ client }: { client: QueryClient }) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [offset, setOffset] = useState(0);
  const [editor, setEditor] = useState<Subject | null | undefined>();
  const [usage, setUsage] = useState<string | null>(null);
  const workspace = useResource<WorkspaceInfo>(client, "/workspace");
  const resource = useResource<SubjectList>(
    client,
    `/subjects?include_archived=${includeArchived}&q=${encodeURIComponent(search)}&limit=40&offset=${offset}`,
  );
  const { busy, error, act } = useAsyncAction();
  const changed = () => {
    client.invalidate("/cases/");
    client.invalidate("/subjects/");
    client
      .fetch("/cases", (signal) => api("/cases", { signal }), true)
      .catch(() => {});
    resource.reload().catch(() => {});
  };
  return (
    <div className="subjects-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">PEOPLE & ORGANIZATIONS</div>
          <h1>主体档案</h1>
          <p>
            分别管理申请人、推荐人、组织和经办人，让每份材料都有清楚的归属。
          </p>
        </div>
        <button className="primary" onClick={() => setEditor(null)}>
          <Plus size={18} />
          新建主体
        </button>
      </div>
      <section className="panel subject-workspace">
        <h2>{workspace.data?.name || "工作空间"}</h2>
        <p>
          当前由你管理这个空间。登录账号负责操作，主体档案记录申请中涉及的人或组织。
        </p>
        {workspace.data && (
          <WorkspaceName
            key={workspace.data.revision}
            workspace={workspace.data}
            saved={() => workspace.reload().catch(() => {})}
          />
        )}
        {workspace.error && (
          <p role="alert">
            {workspace.error.message}
            <button onClick={() => workspace.reload().catch(() => {})}>
              重试
            </button>
          </p>
        )}
      </section>
      <div className="section-toolbar subject-toolbar">
        <form
          className="search-box"
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(query);
            setOffset(0);
          }}
        >
          <Search size={17} />
          <input
            aria-label="搜索主体"
            placeholder="按名称或区分备注搜索"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="text-action">搜索</button>
        </form>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(e) => {
              setIncludeArchived(e.target.checked);
              setOffset(0);
            }}
          />
          包含已归档
        </label>
      </div>
      {(error || resource.error) && (
        <p className="form-error" role="alert">
          {error || resource.error?.message}{" "}
          <button
            className="text-action"
            onClick={() => resource.reload().catch(() => {})}
          >
            刷新列表
          </button>
        </p>
      )}
      {resource.pending && <p role="status">正在读取主体档案…</p>}
      <div className="subject-grid">
        {resource.data?.items.map((subject) => (
          <article className="panel subject-card" key={subject.id}>
            <div className="subject-card-heading">
              {subject.kind === "person" ? (
                <UserRound size={22} />
              ) : (
                <Building2 size={22} />
              )}
              <span>{kindLabels[subject.kind]}</span>
              {subject.archived && (
                <span className="badge unknown">已归档</span>
              )}
            </div>
            <h2>{subject.name}</h2>
            <p>{subject.label || "未填写区分备注"}</p>
            <small className="subject-id">
              {subject.id.slice(0, 8)} · 版本 {subject.revision}
            </small>
            <div className="subject-actions">
              <button
                className="secondary"
                onClick={() => setUsage(subject.id)}
              >
                查看关联
              </button>
              <button className="secondary" onClick={() => setEditor(subject)}>
                编辑档案
              </button>
              <button
                className="text-action"
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await api("/subjects/" + subject.id, {
                      method: "PATCH",
                      body: JSON.stringify({
                        kind: subject.kind,
                        name: subject.name,
                        label: subject.label,
                        attributes: subject.attributes,
                        revision: subject.revision,
                        archived: !subject.archived,
                      }),
                    });
                    changed();
                  })
                }
              >
                {subject.archived ? "恢复档案" : "归档"}
              </button>
            </div>
          </article>
        ))}
      </div>
      {!resource.pending && resource.data?.total === 0 && (
        <Empty
          icon={<UsersRound size={30} />}
          title={search ? "没有匹配的主体" : "从一份主体档案开始"}
          text="为每个人或组织分别建档。同名主体不会自动合并。"
        />
      )}
      {resource.data && resource.data.total > 0 && (
        <div className="subject-pagination">
          <span>
            共 {resource.data.total} 份 · 第 {Math.floor(offset / 40) + 1} 页
          </span>
          <button
            className="secondary"
            disabled={!offset || resource.pending}
            onClick={() => setOffset(offset - 40)}
          >
            上一页
          </button>
          <button
            className="secondary"
            disabled={offset + 40 >= resource.data.total || resource.pending}
            onClick={() => setOffset(offset + 40)}
          >
            下一页
          </button>
        </div>
      )}
      {editor !== undefined && (
        <SubjectEditor
          subject={editor}
          close={() => setEditor(undefined)}
          saved={() => {
            setEditor(undefined);
            changed();
          }}
        />
      )}
      {usage && (
        <SubjectUsage id={usage} client={client} close={() => setUsage(null)} />
      )}
    </div>
  );
}

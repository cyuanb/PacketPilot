import { useState } from "react";
import { CaseLibraryLinks } from "../workflow/CaseLibraryLinks";
import { SimpleRulesDialog } from "../workflow/SimpleRulesDialog";
import {
  BookOpen,
  Check,
  Layers,
  Pencil,
  Plus,
  RefreshCw,
  Sparkles,
  Upload,
} from "lucide-react";
import { post, type Case } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Badge } from "../../components/Badge";
import { Empty } from "../../components/Empty";
type Props = Pick<
  WorkspaceState,
  | "setSource"
  | "setModal"
  | "docSources"
  | "act"
  | "openDoc"
  | "pickUpload"
  | "running"
  | "busy"
  | "run"
  | "setRuleEditor"
  | "refresh"
  | "setNotice"
> & { item: Case };
export function RequirementsPanel({
  setSource,
  setModal,
  docSources,
  act,
  openDoc,
  pickUpload,
  running,
  busy,
  run,
  item,
  setRuleEditor,
  refresh,
  setNotice,
}: Props) {
  const [simpleEditor, setSimpleEditor] = useState(false);
  return (
    <>
      <CaseLibraryLinks item={item} purpose="source" refresh={refresh} />
      <div className="workflow-actions rule-manual-entry">
        <button className="primary" onClick={() => setSimpleEditor(true)}>
          根据通知建立要求
        </button>
        <span className="hint">
          不必编写 JSON；每项要求保留原文引用，保存草稿后再启用。
        </span>
      </div>
      {simpleEditor && (
        <SimpleRulesDialog
          item={item}
          close={() => setSimpleEditor(false)}
          saved={refresh}
        />
      )}
      <div className="rules-layout">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>申请依据</h2>
              <p>以你提供的通知为准，每项要求保留出处</p>
            </div>
            <button
              className="secondary"
              onClick={() => {
                setSource({
                  title: "申请通知",
                  text: "",
                  purpose: "source",
                  category: "",
                });
                setModal("source");
              }}
            >
              <Plus size={16} />
              粘贴通知
            </button>
          </div>
          {docSources.map((d) => (
            <div className="source-row" key={d.id}>
              <BookOpen size={22} />
              <button onClick={() => act(() => openDoc(d))}>
                <strong>{d.title}</strong>
                <small>
                  版本 {d.version} ·{" "}
                  {d.parse_status === "ready" ? "可读取" : "需确认"}
                </small>
              </button>
              <button
                className="icon-button"
                aria-label={"替换" + d.title}
                onClick={() => pickUpload("source", d.id)}
              >
                <RefreshCw size={16} />
              </button>
            </div>
          ))}
          <div className="panel-footer">
            <button
              className="text-action"
              onClick={() => pickUpload("source")}
            >
              <Upload size={15} />
              上传通知文件
            </button>
            <button
              className="primary"
              disabled={!!running || busy || !docSources.length}
              onClick={() => act(() => run("extract"))}
            >
              <Sparkles size={16} />
              提取要求草稿
            </button>
          </div>
        </section>
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>要求版本</h2>
              <p>审阅草稿后启用，检查才会采用这份依据</p>
            </div>
          </div>
          {!item.rule_sets?.length ? (
            <Empty
              icon={<Layers size={27} />}
              title="还没有要求草稿"
              text="先添加通知，再让齐备整理其中的申请要求。"
            />
          ) : (
            item.rule_sets.map((rs) => (
              <div className="rule-version" key={rs.id}>
                <div className="rule-version-title">
                  <h3>
                    版本 {rs.version}{" "}
                    <span>{rs.requirements.length} 项要求</span>
                  </h3>
                  <Badge status={rs.status === "active" ? "pass" : "unknown"}>
                    {
                      (
                        {
                          active: "当前使用",
                          draft: "待审阅",
                          superseded: "历史版本",
                          source_removed: "来源已移除",
                        } as Record<string, string>
                      )[rs.status]
                    }
                  </Badge>
                </div>
                <div className="rule-chips">
                  {rs.requirements.map((r) => (
                    <span key={r.id}>{r.title}</span>
                  ))}
                </div>
                <div className="rule-actions">
                  <button
                    className="secondary"
                    onClick={() => setRuleEditor(rs.requirements)}
                  >
                    <Pencil size={15} />
                    审阅与编辑
                  </button>
                  {rs.status === "draft" && (
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() =>
                        act(async () => {
                          await post("/rule-sets/" + rs.id + "/activate", {
                            revision: item.revision,
                          });
                          await refresh();
                          setNotice("要求已启用，请重新预检材料");
                        })
                      }
                    >
                      <Check size={16} />
                      确认启用
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </section>
      </div>
    </>
  );
}

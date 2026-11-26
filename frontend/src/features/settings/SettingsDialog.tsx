import { ExternalLink, RefreshCw } from "lucide-react";
import { post } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Dialog } from "../../components/Dialog";
type Props = Pick<
  WorkspaceState,
  "modal" | "error" | "setModal" | "capabilities" | "busy" | "act" | "setNotice"
>;
export function SettingsDialog({
  modal,
  error,
  setModal,
  capabilities,
  busy,
  act,
  setNotice,
}: Props) {
  return (
    <>
      {modal === "settings" && (
        <Dialog
          busy={busy}
          error={error}
          title="设置与连接"
          close={() => setModal("")}
        >
          <div className="settings-section">
            <h3>模型连接</h3>
            <p>
              当前模型：<strong>{capabilities?.model}</strong>
            </p>
            <p>{capabilities?.inference}</p>
            <button
              className="secondary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const r = await post<{ ok: boolean; message?: string }>(
                    "/model/check",
                  );
                  setNotice(
                    r.ok ? "模型连接正常" : r.message || "模型连接未成功",
                  );
                })
              }
            >
              <RefreshCw size={16} />
              测试连接
            </button>
          </div>
          <div className="settings-section">
            <h3>文档读取</h3>
            <p>
              支持 PDF、DOCX、TXT、MD
              和图片保存。扫描件与图片需要提供可读副本或校订文本；当前未开启自动
              OCR。
            </p>
          </div>
          <div className="settings-section">
            <h3>本地配置</h3>
            <p>
              模型密钥和数据库凭据通过本地环境配置提供，不进入浏览器。运行数据不进入
              Git 仓库。
            </p>
            <a
              className="text-action"
              href="https://github.com/cyuanb/PacketPilot"
              target="_blank"
              rel="noreferrer"
            >
              项目与使用文档 <ExternalLink size={14} />
            </a>
          </div>
        </Dialog>
      )}
    </>
  );
}

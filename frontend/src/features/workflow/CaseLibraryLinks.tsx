import { FolderOpen } from "lucide-react";
import { useState } from "react";
import type { Case } from "../../api/types";
import { LibraryPicker } from "./LibraryPicker";
import type { DocumentLink } from "./types";

export function CaseLibraryLinks({
  item,
  purpose,
  refresh,
}: {
  item: Case;
  purpose: "source" | "material";
  refresh: () => Promise<void>;
}) {
  const [picker, setPicker] = useState<DocumentLink | null | undefined>();
  const links = (item.document_links || []).filter(
    (link) => link.purpose === purpose,
  );
  return (
    <section className="panel workflow-library">
      <div className="workflow-section-heading">
        <div>
          <h3>资料中心引用</h3>
          <p>每个事项独立固定版本，发现新版后由你决定是否切换。</p>
        </div>
        <button className="secondary" onClick={() => setPicker(null)}>
          <FolderOpen size={16} />
          {purpose === "source" ? "选用已有通知" : "选用已有资料"}
        </button>
      </div>
      {links.length > 0 && (
        <details className="library-version-details">
          <summary>
            已引用 {links.length} 份 ·{" "}
            {links.some((link) => link.update_available)
              ? `${links.filter((link) => link.update_available).length} 份可更新`
              : "查看固定版本"}
          </summary>
          {links.map((link) => (
            <div className="workflow-link" key={link.document_id}>
              <div>
                <strong>{link.asset_title}</strong>
                <p>
                  本事项使用 v{link.version}
                  {link.update_available
                    ? ` · 资料中心已有 v${link.latest_version}`
                    : " · 已是最新资料版本"}
                  {link.archived ? " · 资料已归档" : ""}
                </p>
              </div>
              <button
                className={link.update_available ? "primary" : "text-action"}
                disabled={link.archived}
                onClick={() => setPicker(link)}
              >
                {link.update_available ? "查看并选择新版" : "选择版本"}
              </button>
            </div>
          ))}
        </details>
      )}
      {picker !== undefined && (
        <LibraryPicker
          item={item}
          purpose={purpose}
          link={picker || undefined}
          close={() => setPicker(undefined)}
          saved={refresh}
        />
      )}
    </section>
  );
}

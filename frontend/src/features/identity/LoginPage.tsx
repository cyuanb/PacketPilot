import { AccountEntry } from "../community/AccountTools";
import {
  CheckCircle2,
  FileCheck2,
  FileText,
  LoaderCircle,
  Sparkles,
} from "lucide-react";
import { post } from "../../api";
import type { SessionState } from "./useSession";
type Props = Pick<SessionState, "act" | "setUser" | "error" | "busy">;
export function LoginPage({ act, setUser, error, busy }: Props) {
  return (
    <div className="login-page">
      <div className="login-story">
        <div className="brand">
          <span className="brand-icon">
            <FileCheck2 />
          </span>
          <strong>
            齐备 <small>PacketPilot</small>
          </strong>
        </div>
        <div>
          <span className="eyebrow">从容准备，安心出发</span>
          <h1>
            每一份材料，
            <br />
            都有据可查。
          </h1>
          <p>
            把通知、材料和待办放在一起。
            <br />
            齐备陪你核对细节，补齐每一步。
          </p>
          <div className="login-papers">
            <div>
              <CheckCircle2 />
              申请表 <span>已核对</span>
            </div>
            <div>
              <FileText />
              成绩证明 <span>有据可查</span>
            </div>
            <div>
              <Sparkles />
              下一步 <span>清楚明了</span>
            </div>
          </div>
        </div>
        <span className="login-foot">有依据的预检 · 有条理的申请</span>
      </div>
      <div className="login-form">
        <div>
          <span className="eyebrow">YOUR APPLICATION, TOGETHER</span>
          <h2>欢迎来到齐备</h2>
          <p>登录你的材料准备工作台</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              act(async () => {
                const u = await post<{ username: string }>("/auth/login", {
                  username: f.get("username"),
                  password: f.get("password"),
                });
                setUser(u.username);
              });
            }}
          >
            <label>
              账号
              <input
                name="username"
                defaultValue="owner"
                autoComplete="username"
                required
              />
            </label>
            <label>
              密码
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </label>
            {error && <p className="form-error">{error}</p>}
            <button className="primary login-submit" disabled={busy}>
              {busy ? <LoaderCircle className="spin" size={18} /> : null}
              进入工作台
            </button>
          </form>
          <AccountEntry />
          <p className="login-help">
            首次使用？请使用本地初始化时配置的账号。
            <br />
            原件保存在本机，必要文本片段会发送至配置的模型服务。
          </p>
        </div>
      </div>
    </div>
  );
}

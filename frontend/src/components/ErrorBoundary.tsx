import { Component, type ReactNode } from "react";

export class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <div className="boot" role="alert">
          <div>
            <h2>页面暂时无法显示</h2>
            <p>请重新加载页面。已保存的材料与任务会保留。</p>
            <button
              className="primary"
              onClick={() => window.location.reload()}
            >
              重新加载
            </button>
          </div>
        </div>
      );
    return this.props.children;
  }
}

import { LoaderCircle } from "lucide-react";
import { AuthenticatedWorkspace } from "./app/AuthenticatedWorkspace";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { LoginPage } from "./features/identity/LoginPage";
import { useSession } from "./features/identity/useSession";
function SessionGate() {
  const session = useSession();
  if (session.loading)
    return (
      <div className="boot">
        <LoaderCircle className="spin" /> 正在打开齐备…
      </div>
    );
  if (!session.user)
    return (
      <LoginPage
        act={session.act}
        busy={session.busy}
        error={session.error}
        setUser={session.setUser}
      />
    );
  return (
    <AuthenticatedWorkspace
      key={session.user}
      user={session.user}
      setUser={session.setUser}
    />
  );
}
export default function App() {
  return (
    <ErrorBoundary>
      <SessionGate />
    </ErrorBoundary>
  );
}

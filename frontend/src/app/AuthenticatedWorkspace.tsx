import { useEffect, useState } from "react";
import type { SessionState } from "../features/identity/useSession";
import { QueryClient } from "./queryClient";
import { useWorkspaceRoute } from "./useWorkspaceRoute";
import { Workspace } from "./Workspace";
export function AuthenticatedWorkspace({
  user,
  setUser,
}: {
  user: string;
  setUser: SessionState["setUser"];
}) {
  const navigation = useWorkspaceRoute();
  const [client] = useState(() => new QueryClient());
  const [notice, setNotice] = useState("");
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => () => client.clear(), [client]);
  return (
    <Workspace
      key={
        navigation.selected ||
        navigation.assetId ||
        (navigation.library ? "library-" + navigation.library : undefined) ||
        (navigation.subjects
          ? "subjects"
          : navigation.archive
            ? "archive"
            : "home")
      }
      navigation={navigation}
      client={client}
      user={user}
      setUser={setUser}
      notice={notice}
      notify={setNotice}
    />
  );
}

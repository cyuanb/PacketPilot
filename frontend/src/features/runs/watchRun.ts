type Stream = Pick<EventSource, "addEventListener" | "close">;
type Callbacks = {
  stage: (message: string) => void;
  tool: (name: string) => void;
  done: () => void;
  refreshDetail: (force?: boolean) => Promise<unknown>;
  refreshList: (force?: boolean) => Promise<unknown>;
};

/** A view owns its stream and polling timer; closing it never cancels the server job. */
export function watchRun(
  id: string,
  callbacks: Callbacks,
  connect: (url: string) => Stream = (url) => new EventSource(url),
) {
  let active = true;
  const stream = connect("/api/v1/runs/" + id + "/events");
  const read = (event: Event) => {
    if (!active) return null;
    try {
      return JSON.parse((event as MessageEvent).data);
    } catch {
      return null;
    }
  };
  stream.addEventListener("stage.changed", (event) => {
    const data = read(event);
    if (typeof data?.message === "string") callbacks.stage(data.message);
  });
  stream.addEventListener("tool.started", (event) => {
    const data = read(event);
    if (typeof data?.name === "string") callbacks.tool(data.name);
  });
  const timer = setInterval(() => {
    if (active) callbacks.refreshDetail().catch(() => {});
  }, 2500);
  const close = () => {
    active = false;
    stream.close();
    clearInterval(timer);
  };
  stream.addEventListener("done", () => {
    if (!active) return;
    close();
    callbacks.done();
    // Supersede any poll that started before the terminal event.
    callbacks.refreshDetail(true).catch(() => {});
    callbacks.refreshList(true).catch(() => {});
  });
  return close;
}

export type QueryState<T> = { data?: T; error?: Error; pending: boolean };
type Entry = {
  state: QueryState<unknown>;
  listeners: Set<() => void>;
  generation: number;
  controller?: AbortController;
  promise?: Promise<unknown>;
};

/** Per-session server state. Keys include resource IDs; invalidation fences older responses. */
export class QueryClient {
  private entries = new Map<string, Entry>();

  private entry(key: string) {
    let entry = this.entries.get(key);
    if (!entry) {
      entry = {
        state: { pending: false },
        listeners: new Set(),
        generation: 0,
      };
      this.entries.set(key, entry);
    }
    return entry;
  }

  snapshot<T>(key: string): QueryState<T> {
    return this.entry(key).state as QueryState<T>;
  }

  subscribe(key: string, listener: () => void) {
    const entry = this.entry(key);
    entry.listeners.add(listener);
    return () => {
      entry.listeners.delete(listener);
    };
  }

  private publish(entry: Entry, state: QueryState<unknown>) {
    entry.state = state;
    for (const listener of entry.listeners) listener();
  }

  fetch<T>(
    key: string,
    loader: (signal: AbortSignal) => Promise<T>,
    force = false,
  ): Promise<T> {
    const entry = this.entry(key);
    if (entry.promise && !force) return entry.promise as Promise<T>;
    entry.controller?.abort();
    const controller = new AbortController();
    const generation = ++entry.generation;
    entry.controller = controller;
    // Install the promise before notifying observers, allowing safe request deduplication.
    const promise = Promise.resolve()
      .then(() => loader(controller.signal))
      .then(
        (data) => {
          if (entry.generation === generation)
            this.publish(entry, { data, pending: false });
          return data;
        },
        (cause: unknown) => {
          const error =
            cause instanceof Error ? cause : new Error(String(cause));
          if (entry.generation === generation) {
            this.publish(entry, {
              data: entry.state.data,
              error,
              pending: false,
            });
          }
          throw error;
        },
      )
      .finally(() => {
        if (entry.generation === generation) {
          entry.promise = undefined;
          entry.controller = undefined;
        }
      });
    entry.promise = promise;
    this.publish(entry, { data: entry.state.data, pending: true });
    return promise;
  }

  set<T>(key: string, data: T) {
    const entry = this.entry(key);
    ++entry.generation;
    entry.controller?.abort();
    entry.promise = undefined;
    entry.controller = undefined;
    this.publish(entry, { data, pending: false });
  }

  invalidate(prefix: string) {
    for (const [key, entry] of this.entries) {
      if (!key.startsWith(prefix)) continue;
      ++entry.generation;
      entry.controller?.abort();
      entry.promise = undefined;
      entry.controller = undefined;
      this.publish(entry, { pending: false });
    }
  }

  clear() {
    for (const entry of this.entries.values()) {
      ++entry.generation;
      entry.controller?.abort();
      entry.promise = undefined;
      entry.controller = undefined;
      this.publish(entry, { pending: false });
    }
    this.entries.clear();
  }
}

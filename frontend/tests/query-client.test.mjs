import assert from "node:assert/strict";
import { test } from "node:test";
import { QueryClient } from "../src/app/queryClient.ts";

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("concurrent reads share a request and publish stable snapshots", async () => {
  const client = new QueryClient(), request = deferred();
  let calls = 0, notifications = 0;
  const off = client.subscribe("/cases/a", () => notifications++);
  const loader = () => { calls++; return request.promise; };
  const first = client.fetch("/cases/a", loader);
  assert.equal(client.fetch("/cases/a", loader), first);
  assert.equal(client.snapshot("/cases/a"), client.snapshot("/cases/a"));
  request.resolve({ id: "a", revision: 1 });
  await first;
  assert.equal(calls, 1);
  assert.equal(notifications, 2);
  assert.equal(client.snapshot("/cases/a").data.id, "a");
  off();
  client.set("/cases/a", { revision: 2 });
  assert.equal(notifications, 2);
});

test("switching cases keeps late responses under their own key", async () => {
  const client = new QueryClient(), slow = deferred();
  const a = client.fetch("/cases/a", () => slow.promise);
  await client.fetch("/cases/b", async () => ({ id: "b" }));
  slow.resolve({ id: "a" });
  await a;
  assert.equal(client.snapshot("/cases/b").data.id, "b");
  assert.equal(client.snapshot("/cases/a").data.id, "a");
});

test("refresh aborts and fences an older poll even if transport ignores abort", async () => {
  const client = new QueryClient(), slow = deferred();
  let signal;
  const old = client.fetch("/cases/a", (value) => { signal = value; return slow.promise; });
  await Promise.resolve();
  await client.fetch("/cases/a", async () => ({ revision: 2 }), true);
  assert.equal(signal.aborted, true);
  slow.resolve({ revision: 1 });
  await old;
  assert.equal(client.snapshot("/cases/a").data.revision, 2);
});

test("superseded errors cannot overwrite a successful refresh", async () => {
  const client = new QueryClient(), slow = deferred();
  const old = client.fetch("/cases/a", () => slow.promise);
  const rejection = assert.rejects(old, /old failure/);
  await client.fetch("/cases/a", async () => ({ revision: 2 }), true);
  slow.reject(new Error("old failure"));
  await rejection;
  assert.equal(client.snapshot("/cases/a").error, undefined);
  assert.equal(client.snapshot("/cases/a").data.revision, 2);
});

test("query failures are retryable without discarding existing data", async () => {
  const client = new QueryClient();
  client.set("/cases/a", { revision: 1 });
  await assert.rejects(client.fetch("/cases/a", async () => { throw new Error("offline"); }), /offline/);
  assert.equal(client.snapshot("/cases/a").data.revision, 1);
  assert.equal(client.snapshot("/cases/a").error.message, "offline");
  await client.fetch("/cases/a", async () => ({ revision: 2 }));
  assert.equal(client.snapshot("/cases/a").error, undefined);
  assert.equal(client.snapshot("/cases/a").data.revision, 2);
});

test("logout clears cached materials and fences late responses", async () => {
  const client = new QueryClient(), slow = deferred();
  client.set("/cases/b", { title: "session data" });
  const old = client.fetch("/cases/a", () => slow.promise);
  client.clear();
  slow.resolve({ title: "late session data" });
  await old;
  assert.equal(client.snapshot("/cases/a").data, undefined);
  assert.equal(client.snapshot("/cases/b").data, undefined);
});

test("a mutation response supersedes an in-flight detail read", async () => {
  const client = new QueryClient(), slow = deferred();
  const old = client.fetch("/cases/a", () => slow.promise);
  client.set("/cases/a", { revision: 3 });
  slow.resolve({ revision: 2 });
  await old;
  assert.equal(client.snapshot("/cases/a").data.revision, 3);
});

test("profile changes invalidate case details and fence old snapshots without clearing other queries", async () => {
  const client = new QueryClient(), slow = deferred();
  client.set("/workspace", { name: "Workspace" });
  client.set("/cases/a", { revision: 1 });
  const old = client.fetch("/cases/a", () => slow.promise);
  client.invalidate("/cases/");
  slow.resolve({ revision: 1 });
  await old;
  assert.equal(client.snapshot("/cases/a").data, undefined);
  assert.equal(client.snapshot("/workspace").data.name, "Workspace");
  await client.fetch("/cases/a", async () => ({ revision: 2 }));
  assert.equal(client.snapshot("/cases/a").data.revision, 2);
});

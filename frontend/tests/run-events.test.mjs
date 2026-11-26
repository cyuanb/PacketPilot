import assert from "node:assert/strict";
import { test } from "node:test";
import { watchRun } from "../src/features/runs/watchRun.ts";

function fixture() {
  const handlers = new Map(), stages = [], tools = [], details = [], lists = [];
  let closes = 0, done = 0;
  const stop = watchRun("run-a", {
    stage: (s) => stages.push(s), tool: (s) => tools.push(s), done: () => done++,
    refreshDetail: async (force) => details.push(force), refreshList: async (force) => lists.push(force),
  }, (url) => {
    assert.equal(url, "/api/v1/runs/run-a/events");
    return { addEventListener: (name, handler) => handlers.set(name, handler), close: () => closes++ };
  });
  return { stop, stages, tools, details, lists, closes: () => closes, done: () => done,
    emit: (name, data) => handlers.get(name)({ data: typeof data === "string" ? data : JSON.stringify(data) }) };
}

test("malformed progress does not crash the view", (t) => {
  t.mock.timers.enable({ apis: ["setInterval"] });
  const f = fixture();
  f.emit("stage.changed", "bad JSON");
  f.emit("tool.started", {});
  f.emit("stage.changed", { message: "Reading" });
  f.emit("tool.started", { name: "read_document" });
  assert.deepEqual(f.stages, ["Reading"]);
  assert.deepEqual(f.tools, ["read_document"]);
  f.stop();
});
test("leaving releases the stream and timer and ignores queued events", (t) => {
  t.mock.timers.enable({ apis: ["setInterval"] });
  const f = fixture();
  t.mock.timers.tick(2500);
  assert.equal(f.details.length, 1);
  f.stop();
  f.emit("stage.changed", { message: "Late event" });
  f.emit("done", {});
  t.mock.timers.tick(10000);
  assert.deepEqual(f.stages, []);
  assert.equal(f.details.length, 1);
  assert.equal(f.closes(), 1);
  assert.equal(f.done(), 0);
});
test("terminal events force a fresh read and stop polling", (t) => {
  t.mock.timers.enable({ apis: ["setInterval"] });
  const f = fixture();
  f.emit("done", {});
  f.emit("done", {});
  t.mock.timers.tick(10000);
  assert.deepEqual(f.details, [true]);
  assert.deepEqual(f.lists, [true]);
  assert.equal(f.done(), 1);
  f.stop();
});

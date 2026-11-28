import assert from "node:assert/strict";
import { test } from "node:test";
import { date } from "../src/lib/format.ts";

test("calendar deadlines keep their day across browser time zones", () => {
  const original = process.env.TZ;
  try {
    process.env.TZ = "America/Los_Angeles";
    assert.equal(date("2026-12-18"), "12月18日");
    process.env.TZ = "Asia/Shanghai";
    assert.equal(date("2026-12-18"), "12月18日");
    assert.equal(date("2026-02-31"), "待确认");
    assert.equal(date("unknown"), "待确认");
  } finally {
    if (original === undefined) delete process.env.TZ;
    else process.env.TZ = original;
  }
});

import assert from "node:assert/strict";
import { test } from "node:test";
import { parseRoute, routeHash, tabs } from "../src/app/routes.ts";
const id = "12345678-1234-1234-1234-123456789abc";

test("legacy links preserve the selected case", () => {
  assert.equal(routeHash(parseRoute("#case/" + id)), "#/cases/" + id + "/overview");
});
test("each case tab survives URL round trips", () => {
  for (const tab of tabs) {
    const route = { selected: id, tab, archive: false };
    assert.deepEqual(parseRoute(routeHash(route)), route);
  }
});
test("list and archive routes remain distinct", () => {
  assert.equal(parseRoute("#/archive").archive, true);
  assert.equal(routeHash(parseRoute("")), "#/cases");
});
test("invalid routes and tabs have safe fallbacks", () => {
  assert.equal(parseRoute("#/cases/not-an-id/documents").selected, null);
  assert.equal(parseRoute("#/cases/" + id + "/missing-tab").tab, "overview");
  assert.equal(parseRoute("#case/" + id + "/overview/extra").selected, null);
});

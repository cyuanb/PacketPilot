import assert from "node:assert/strict";
import { test } from "node:test";
import { allowsRole, subjectCaption } from "../src/features/subjects/labels.ts";

test("person and organization roles stay distinct", () => {
  assert.equal(allowsRole("organization", "applicant"), true);
  assert.equal(allowsRole("person", "applicant"), true);
  assert.equal(allowsRole("organization", "representative"), false);
  assert.equal(allowsRole("organization", "recommender"), false);
  assert.equal(allowsRole("person", "organization"), false);
  assert.equal(allowsRole("person", "representative"), true);
});
test("same names retain a visible distinguishing label and identity", () => {
  const a = { id: "12345678-a", name: "同名", kind: "person", label: "申请人" };
  const b = { ...a, id: "87654321-b", label: "推荐人" };
  assert.notEqual(subjectCaption(a), subjectCaption(b));
  assert.match(subjectCaption(a), /申请人.*12345678/);
  assert.match(subjectCaption(b), /推荐人.*87654321/);
});

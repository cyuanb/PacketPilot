import assert from "node:assert/strict";
import { test } from "node:test";
import { checkReadiness } from "../src/features/cases/checkReadiness.ts";

test("all check entry points use current source parse revisions", () => {
  const item = {documents:[{id:"notice",purpose:"source",parse_status:"ready",parse_revision_id:"p2"}],
    checklist:{requirements:[{source_evidence:[{document_id:"notice",parse_revision_id:"p1"}]}]}};
  assert.equal(checkReadiness(item).canCheck, false);
  item.checklist.requirements[0].source_evidence[0].parse_revision_id = "p2";
  assert.equal(checkReadiness(item).canCheck, true);
  item.scenario = {primary_subject_kind:"person"};
  item.subjects = [{role:"applicant",kind:"person",archived:true}];
  assert.equal(checkReadiness(item).canCheck, false);
  item.subjects[0].archived = false;
  assert.equal(checkReadiness(item).canCheck, true);
});

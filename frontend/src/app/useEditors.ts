import { useState } from "react";
import { type Doc, type Evidence, type Requirement } from "../api";
export function useEditors() {
  const [source, setSource] = useState({
    title: "申请通知",
    text: "",
    purpose: "source",
    category: "",
  });
  const [draftCase, setDraftCase] = useState({
    title: "",
    institution: "",
    kind: "exchange",
    deadline: "",
  });
  const [preview, setPreview] = useState<Doc | null>(null),
    [highlight, setHighlight] = useState<Evidence | null>(null);
  const [rules, setRules] = useState<Requirement[]>([]),
    [rulesRaw, setRulesRaw] = useState(""),
    [advanced, setAdvanced] = useState(false);
  const [facts, setFacts] = useState<[string, string][]>([]),
    [manual, setManual] = useState(""),
    [manualNote, setManualNote] = useState("");
  const [correction, setCorrection] = useState(""),
    [confirm, setConfirm] = useState<{
      text: string;
      action: () => Promise<void>;
    } | null>(null);
  const [capabilities, setCapabilities] = useState<{
    model: string;
    model_configured: boolean;
    ocr: boolean;
    inference: string;
  } | null>(null);
  return {
    source,
    setSource,
    draftCase,
    setDraftCase,
    preview,
    setPreview,
    highlight,
    setHighlight,
    rules,
    setRules,
    rulesRaw,
    setRulesRaw,
    advanced,
    setAdvanced,
    facts,
    setFacts,
    manual,
    setManual,
    manualNote,
    setManualNote,
    correction,
    setCorrection,
    confirm,
    setConfirm,
    capabilities,
    setCapabilities,
  };
}

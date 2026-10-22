/** Pure reducer from SSE events to what the workspace shows; tested without a browser. */
import type { ApprovalState } from "@/components/cards/ApprovalCard";
import type { PlanProposal } from "@/components/cards/PlanCard";
import type { RepoAnalysis } from "@/components/cards/RepoAnalysisCard";
import type { Step } from "@/components/checklist/RunChecklist";
import type { Risk } from "./api";
import type { ApprovalRequested, RunEvent } from "./sse";

export type ChatItem =
  | { kind: "user"; id: string; text: string }
  | { kind: "assistant"; id: string; text: string; done: boolean }
  | { kind: "tool"; id: string; name: string; risk?: Risk; status: "called" | "ok" | "limitation" | "error" }
  | { kind: "approval"; id: string; card: ApprovalRequested; state: ApprovalState; error?: string }
  | { kind: "limitation"; id: string; message_fa: string; workaround_fa?: string }
  | { kind: "human_only"; id: string; task: string; steps_fa: string[] }
  | { kind: "repo_analysis"; id: string; data: RepoAnalysis }
  | { kind: "github_reconnect"; id: string; message_fa: string }
  | { kind: "plan_proposal"; id: string; data: PlanProposal };

export type RunPhase = "idle" | "running" | "awaiting_approval" | "succeeded" | "failed" | "cancelled";

export interface View {
  phase: RunPhase;
  steps: Step[];
  items: ChatItem[];
  summary_fa?: string;
}

export const emptyView: View = { phase: "idle", steps: [], items: [] };

let counter = 0;
const localId = (p: string) => `${p}-${++counter}`;

export function addUserMessage(v: View, text: string): View {
  return { ...v, phase: "running", steps: [], summary_fa: undefined, items: [...v.items, { kind: "user", id: localId("u"), text }] };
}

function patchItem(v: View, match: (i: ChatItem) => boolean, patch: (i: ChatItem) => ChatItem): View {
  const idx = v.items.findLastIndex(match);
  if (idx < 0) return v;
  const items = v.items.slice();
  items[idx] = patch(items[idx]);
  return { ...v, items };
}

export function setApproval(v: View, approvalId: string, state: ApprovalState, error?: string): View {
  return patchItem(
    v,
    (i) => i.kind === "approval" && i.id === approvalId,
    (i) => ({ ...(i as Extract<ChatItem, { kind: "approval" }>), state, error }),
  );
}

export function applyEvent(v: View, e: RunEvent): View {
  switch (e.type) {
    case "run.started":
      return { ...v, phase: "running", steps: e.data.steps.map((s) => ({ ...s, status: "pending" })) };
    case "run.status":
      return { ...v, phase: e.data.status === "awaiting_approval" ? "awaiting_approval" : "running" };
    case "step.started":
    case "step.done":
    case "step.failed": {
      const status = e.type === "step.started" ? "running" : e.type === "step.done" ? "done" : "failed";
      return {
        ...v,
        steps: v.steps.map((s) =>
          s.key === e.data.key ? { ...s, status, duration_ms: e.data.duration_ms, error_fa: e.data.error?.message_fa } : s,
        ),
      };
    }
    case "message.delta": {
      const exists = v.items.some((i) => i.kind === "assistant" && i.id === e.data.message_id);
      if (!exists) {
        return { ...v, items: [...v.items, { kind: "assistant", id: e.data.message_id, text: e.data.text, done: false }] };
      }
      return patchItem(
        v,
        (i) => i.kind === "assistant" && i.id === e.data.message_id,
        (i) => ({ ...(i as Extract<ChatItem, { kind: "assistant" }>), text: `${(i as { text: string }).text}\n\n${e.data.text}` }),
      );
    }
    case "message.done": {
      const exists = v.items.some((i) => i.kind === "assistant" && i.id === e.data.message_id);
      if (!exists && !e.data.text) return v;
      if (!exists) return { ...v, items: [...v.items, { kind: "assistant", id: e.data.message_id, text: e.data.text, done: true }] };
      return patchItem(
        v,
        (i) => i.kind === "assistant" && i.id === e.data.message_id,
        (i) => ({ ...(i as Extract<ChatItem, { kind: "assistant" }>), text: e.data.text, done: true }),
      );
    }
    case "tool.called":
      return { ...v, items: [...v.items, { kind: "tool", id: localId("t"), name: e.data.name, risk: e.data.risk, status: "called" }] };
    case "tool.result":
      return patchItem(
        v,
        (i) => i.kind === "tool" && i.name === e.data.name && i.status === "called",
        (i) => ({ ...(i as Extract<ChatItem, { kind: "tool" }>), status: e.data.status }),
      );
    case "approval.requested":
      return {
        ...v,
        phase: "awaiting_approval",
        steps: v.steps.map((s) => (s.status === "running" ? { ...s, status: "blocked" } : s)),
        items: [...v.items, { kind: "approval", id: e.data.approval_id, card: e.data, state: "pending" }],
      };
    case "approval.resolved": {
      const next = setApproval(v, e.data.approval_id, e.data.status as ApprovalState);
      return { ...next, steps: next.steps.map((s) => (s.status === "blocked" ? { ...s, status: "running" } : s)) };
    }
    case "card": {
      const p = e.data.payload as Record<string, unknown>;
      if (e.data.card_type === "limitation") {
        return { ...v, items: [...v.items, { kind: "limitation", id: localId("l"), message_fa: String(p.message_fa ?? ""), workaround_fa: p.workaround_fa as string | undefined }] };
      }
      if (e.data.card_type === "human_only") {
        return { ...v, items: [...v.items, { kind: "human_only", id: localId("h"), task: String(p.task ?? ""), steps_fa: (p.steps_fa as string[]) ?? [] }] };
      }
      if (e.data.card_type === "repo_analysis") {
        return { ...v, items: [...v.items, { kind: "repo_analysis", id: localId("r"), data: p as unknown as RepoAnalysis }] };
      }
      if (e.data.card_type === "plan_proposal") {
        return { ...v, items: [...v.items, { kind: "plan_proposal", id: localId("p"), data: p as unknown as PlanProposal }] };
      }
      if (e.data.card_type === "github_reconnect") {
        return { ...v, items: [...v.items, { kind: "github_reconnect", id: localId("g"), message_fa: String(p.message_fa ?? "") }] };
      }
      return v; // other cards land with their tasks (B-10, B-13, B-19)
    }
    case "run.done":
      return { ...v, phase: e.data.status, summary_fa: e.data.summary_fa };
    default:
      return v;
  }
}

/** Run events over SSE. EventSource reconnects on its own and sends Last-Event-ID, so the agent
 * replays what was missed; we close it ourselves on run.done. */

export interface StepRef {
  key: string;
  title_fa: string;
}

export type RunEvent =
  | { type: "run.started"; data: { mode: string; steps: StepRef[] } }
  | { type: "run.status"; data: { status: string } }
  | { type: "step.started" | "step.done" | "step.failed"; data: StepEventData }
  | { type: "step.progress"; data: { step_id: string; text: string; log_tail?: string[] } }
  | { type: "message.delta" | "message.done"; data: { message_id: string; text: string } }
  | { type: "tool.called" | "tool.result"; data: ToolEventData }
  | { type: "card"; data: { card_type: string; payload: Record<string, unknown> } }
  | { type: "approval.requested"; data: ApprovalRequested }
  | { type: "approval.resolved"; data: { approval_id: string; status: string; reason_fa?: string } }
  | { type: "run.done"; data: { status: "succeeded" | "failed" | "cancelled"; summary_fa?: string } };

export interface StepEventData {
  step_id: string;
  key: string;
  title_fa: string;
  duration_ms?: number;
  error?: { code: string; message_fa: string };
}

export interface ToolEventData {
  tool_call_id?: string;
  name: string;
  risk?: "read" | "sensitive" | "human_only";
  status: "called" | "ok" | "limitation" | "error";
}

export interface ApprovalRequested {
  approval_id: string;
  tool: string;
  summary_fa: string;
  why_fa?: string;
  cost_delta_toman?: number;
  cost_source?: { source: string; observed_at: string };
  changes?: Record<string, unknown>;
  expires_at: string;
  signature: string;
}

export const EVENT_TYPES: RunEvent["type"][] = [
  "run.started", "run.status", "step.started", "step.done", "step.failed", "step.progress",
  "message.delta", "message.done", "tool.called", "tool.result", "card",
  "approval.requested", "approval.resolved", "run.done",
];

export function subscribeRun(
  runId: string,
  onEvent: (e: RunEvent) => void,
  onConnection: (state: "open" | "reconnecting") => void,
): () => void {
  const es = new EventSource(`/api/runs/${runId}/events`);
  es.onopen = () => onConnection("open");
  es.onerror = () => onConnection("reconnecting");
  for (const type of EVENT_TYPES) {
    es.addEventListener(type, (msg) => {
      const env = JSON.parse((msg as MessageEvent).data);
      onEvent({ type, data: env.data } as RunEvent);
      if (type === "run.done") es.close();
    });
  }
  return () => es.close();
}

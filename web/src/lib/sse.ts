/** Run events over SSE. EventSource retries on its own (with Last-Event-ID) only after a network drop; when a
 * proxy answers the retry with an error it gives up for good (readyState CLOSED, as on Liara mid-deploy), so
 * then we open a new one from the last event id (?after=) and the agent replays what was missed. */

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
  danger?: boolean; // irreversible (a delete): red card
  confirm_text?: string | null; // typed by the user before the slider unlocks; the server checks it too
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
  let es: EventSource;
  let last = "";
  let done = false;
  let retry: ReturnType<typeof setTimeout> | undefined;
  const open = () => {
    es = new EventSource(`/api/runs/${runId}/events${last ? `?after=${encodeURIComponent(last)}` : ""}`);
    es.onopen = () => onConnection("open");
    es.onerror = () => {
      onConnection("reconnecting");
      if (es.readyState === EventSource.CLOSED && !done) retry = setTimeout(open, 2000);
    };
    for (const type of EVENT_TYPES) {
      es.addEventListener(type, (msg) => {
        const m = msg as MessageEvent;
        if (m.lastEventId) last = m.lastEventId;
        onEvent({ type, data: JSON.parse(m.data).data } as RunEvent);
        if (type === "run.done") {
          done = true;
          es.close();
        }
      });
    }
  };
  open();
  return () => {
    done = true;
    clearTimeout(retry);
    es.close();
  };
}

/** A finished run's saved events, read in one go (the stream ends at run.done), for reopening a chat. */
export async function fetchRunEvents(runId: string): Promise<RunEvent[]> {
  const res = await fetch(`/api/runs/${runId}/events`, { credentials: "same-origin" });
  return res.ok ? parseSse(await res.text()) : [];
}

export function parseSse(body: string): RunEvent[] {
  const out: RunEvent[] = [];
  for (const block of body.split("\n\n")) {
    let type = "";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) type = line.slice(7);
      else if (line.startsWith("data: ")) data += line.slice(6);
    }
    if (type && data && (EVENT_TYPES as string[]).includes(type)) {
      out.push({ type, data: JSON.parse(data).data } as RunEvent);
    }
  }
  return out;
}

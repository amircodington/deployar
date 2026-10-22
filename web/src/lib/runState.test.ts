import { describe, expect, it } from "vitest";
import { addUserMessage, applyEvent, emptyView } from "./runState";
import type { RunEvent } from "./sse";

const run: RunEvent[] = [
  { type: "run.started", data: { mode: "chat", steps: [{ key: "answer", title_fa: "پاسخ" }] } },
  { type: "step.started", data: { step_id: "s1", key: "answer", title_fa: "پاسخ" } },
  { type: "message.delta", data: { message_id: "m1", text: "نگاه می‌کنم." } },
  { type: "tool.called", data: { name: "restart_app", risk: "sensitive", status: "called" } },
  {
    type: "approval.requested",
    data: { approval_id: "a1", tool: "restart_app", summary_fa: "ری‌استارت", expires_at: "2026-10-22T10:00:00Z", signature: "x.y" },
  },
];

describe("run state", () => {
  it("follows a run into an approval and out of it", () => {
    let v = run.reduce(applyEvent, addUserMessage(emptyView, "ری‌استارت کن"));
    expect(v.phase).toBe("awaiting_approval");
    expect(v.steps[0].status).toBe("blocked");
    expect(v.items.map((i) => i.kind)).toEqual(["user", "assistant", "tool", "approval"]);

    v = applyEvent(v, { type: "approval.resolved", data: { approval_id: "a1", status: "approved" } });
    v = applyEvent(v, { type: "tool.result", data: { name: "restart_app", status: "ok" } });
    v = applyEvent(v, { type: "message.done", data: { message_id: "m1", text: "انجام شد." } });
    v = applyEvent(v, { type: "step.done", data: { step_id: "s1", key: "answer", title_fa: "پاسخ" } });
    v = applyEvent(v, { type: "run.done", data: { status: "succeeded" } });

    expect(v.phase).toBe("succeeded");
    expect(v.steps[0].status).toBe("done");
    const approval = v.items.find((i) => i.kind === "approval");
    expect(approval && approval.kind === "approval" && approval.state).toBe("approved");
    const tool = v.items.find((i) => i.kind === "tool");
    expect(tool && tool.kind === "tool" && tool.status).toBe("ok");
    const answer = v.items.find((i) => i.kind === "assistant");
    expect(answer && answer.kind === "assistant" && answer.text).toBe("انجام شد.");
  });

  it("limitation and human-only cards become chat items", () => {
    const v = applyEvent(emptyView, {
      type: "card",
      data: { card_type: "limitation", payload: { message_fa: "نمی‌شود", workaround_fa: "این کار را بکن" } },
    });
    expect(v.items[0]).toMatchObject({ kind: "limitation", message_fa: "نمی‌شود" });
  });

  it("keeps one build card per deployment and updates it in place", () => {
    const card = (state: string, line: string): RunEvent => ({
      type: "card",
      data: { card_type: "deploy_progress", payload: { deployment_id: "d1", app: "torob-gard", state, log_tail: [line] } },
    });
    let v = [card("BUILDING", "Step 1/5"), card("DEPLOYING", "Step 5/5")].reduce(applyEvent, emptyView);
    expect(v.items).toHaveLength(1);
    expect(v.items[0].kind === "deploy_progress" && v.items[0].data.state).toBe("DEPLOYING");
    v = applyEvent(v, { type: "card", data: { card_type: "live_url", payload: { url: "https://torob-gard.liara.run" } } });
    expect(v.items.map((i) => i.kind)).toEqual(["deploy_progress", "live_url"]);
  });
});

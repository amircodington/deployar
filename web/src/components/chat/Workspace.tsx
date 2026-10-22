"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AppsCard, StatTiles } from "@/components/dash/Overview";
import { RunChecklist } from "@/components/checklist/RunChecklist";
import { StatusChip } from "@/components/ui";
import { AgentError, api } from "@/lib/api";
import { fa } from "@/lib/fa";
import { addUserMessage, applyEvent, emptyView, markEnvSent, setApproval, type View } from "@/lib/runState";
import { subscribeRun } from "@/lib/sse";
import { useDashboard } from "@/lib/useDashboard";
import { Composer } from "./Composer";
import { MessageList } from "./MessageList";

const STATE_LINE: Record<View["phase"], string> = {
  idle: fa.stateIdle,
  running: fa.stateWorking,
  awaiting_approval: fa.stateWaiting,
  succeeded: fa.stateDone,
  failed: fa.stateFailed,
  cancelled: fa.stateFailed,
};

/** Home: greeting, live tiles, the conversation with its cards, and the run checklist beside it. */
export function Workspace({ projectId }: { projectId?: string }) {
  const [view, setView] = useState<View>(emptyView);
  const [reconnecting, setReconnecting] = useState(false);
  const conversation = useRef<string | undefined>(undefined);
  const unsubscribe = useRef<() => void>(() => {});
  const bottom = useRef<HTMLDivElement>(null);
  const dash = useDashboard();
  const { reload } = dash;

  useEffect(() => () => unsubscribe.current(), []);
  useEffect(() => {
    if (view.items.length) bottom.current?.scrollIntoView({ block: "end", behavior: "smooth" }); // never return it
  }, [view.items.length]);
  useEffect(() => {
    if (view.phase === "succeeded" || view.phase === "failed") reload(); // an action may have changed credit or apps
  }, [view.phase, reload]);

  const send = useCallback(
    async (text: string) => {
      setView((v) => addUserMessage(v, text));
      try {
        const { run_id, conversation_id } = await api.startRun({
          text,
          project_id: projectId,
          conversation_id: conversation.current,
        });
        conversation.current = conversation_id;
        unsubscribe.current();
        unsubscribe.current = subscribeRun(
          run_id,
          (e) => setView((v) => applyEvent(v, e)),
          (s) => setReconnecting(s === "reconnecting"),
        );
      } catch (err) {
        const message = err instanceof AgentError ? err.message : fa.connectionLost;
        setView((v) => ({ ...v, phase: "failed", summary_fa: message }));
      }
    },
    [projectId],
  );

  const decide = useCallback(async (approvalId: string, decision: "approve" | "reject") => {
    const item = view.items.find((i) => i.kind === "approval" && i.id === approvalId);
    if (!item || item.kind !== "approval") return;
    setView((v) => setApproval(v, approvalId, "approving"));
    try {
      const { status } = await api.decide(approvalId, decision, item.card.signature);
      setView((v) => setApproval(v, approvalId, status as "approved" | "rejected"));
    } catch (err) {
      const message = err instanceof AgentError ? err.message : fa.decisionFailed;
      const final = err instanceof AgentError && err.status === 409;
      setView((v) => setApproval(v, approvalId, final ? "expired" : "pending", message));
    }
  }, [view.items]);

  const busy = view.phase === "running" || view.phase === "awaiting_approval";

  return (
    <div className="flex flex-1 flex-col gap-5 px-4 pb-4 pt-4 md:gap-6 md:px-8">
      <section>
        <p className="text-[32px] font-light leading-10 text-ink-faint md:text-[44px] md:leading-[52px]">{fa.hello}</p>
        <p key={view.phase} className="rise text-[32px] font-extrabold leading-10 md:text-[44px] md:leading-[52px]">
          {STATE_LINE[view.phase]}
        </p>
        {view.summary_fa && <p className="rise mt-2 text-[15px] text-ink-muted">{view.summary_fa}</p>}
      </section>

      <StatTiles data={dash.data} phase={view.phase} />

      <div className="grid flex-1 grid-cols-[minmax(0,1fr)] gap-4 md:gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section
          className="tile-in flex min-h-[460px] min-w-0 flex-col rounded-[28px] bg-card"
          style={{ "--i": 4 } as React.CSSProperties}
        >
          <header className="flex items-center gap-3 px-5 pt-5">
            <h2 className="flex-1 text-lg font-medium">{fa.conversation}</h2>
            <StatusChip tone={busy ? (view.phase === "awaiting_approval" ? "warn" : "ok") : "off"} live={busy}>
              {fa.phase[view.phase]}
            </StatusChip>
          </header>

          <div className="flex flex-1 flex-col gap-4 px-4 py-4 md:px-5">
            {view.steps.length > 0 && (
              <div className="rounded-[20px] bg-raised/50 p-3 lg:hidden">
                <RunChecklist steps={view.steps} />
              </div>
            )}
            {view.items.length === 0 ? (
              <div className="flex flex-1 flex-col justify-end gap-3">
                <p className="text-[13px] text-ink-muted">{fa.tryThese}</p>
                <div className="flex flex-wrap gap-2">
                  {fa.suggestions.map((s, i) => (
                    <button
                      key={s.label}
                      type="button"
                      onClick={() => send(s.text)}
                      className="pressable tile-in max-w-full truncate rounded-full border border-line px-4 py-2.5 text-start text-[14px] hover:bg-raised"
                      style={{ "--i": 6 + i } as React.CSSProperties}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <MessageList
                items={view.items}
                onDecide={decide}
                onEnvDone={(id, refs) => {
                  setView((v) => markEnvSent(v, id));
                  send(fa.envMessage(refs.map((r) => `${r.key}=${r.value_ref}`).join("، ")));
                }}
              />
            )}
            {reconnecting && busy && <p className="text-[13px] text-ink-muted">{fa.connectionLost}</p>}
            <div ref={bottom} />
          </div>

          <div className="sticky bottom-0 rounded-b-[28px] bg-card/90 px-3 pb-[calc(12px+env(safe-area-inset-bottom,0px))] pt-2 backdrop-blur md:px-4 md:pb-4">
            <Composer onSend={send} busy={busy} />
          </div>
        </section>

        <aside className="flex flex-col gap-4 md:gap-6">
          <section
            className="tile-in hidden rounded-[28px] bg-card p-5 lg:block"
            style={{ "--i": 5 } as React.CSSProperties}
          >
            <h2 className="mb-3 text-lg font-medium">{fa.checklist}</h2>
            <RunChecklist steps={view.steps} />
          </section>
          <AppsCard data={dash.data} />
        </aside>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { RunChecklist } from "@/components/checklist/RunChecklist";
import { AgentError, api } from "@/lib/api";
import { fa } from "@/lib/fa";
import { addUserMessage, applyEvent, emptyView, setApproval, type View } from "@/lib/runState";
import { subscribeRun } from "@/lib/sse";
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

/** The shell: greeting, conversation with cards, live checklist (side panel on desktop, inline on phone). */
export function Workspace({ projectId }: { projectId?: string }) {
  const [view, setView] = useState<View>(emptyView);
  const [reconnecting, setReconnecting] = useState(false);
  const conversation = useRef<string | undefined>(undefined);
  const unsubscribe = useRef<() => void>(() => {});
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => () => unsubscribe.current(), []);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" }); // returns a Promise in newer browsers; never return it
  }, [view.items.length]);

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
    <div className="mx-auto flex min-h-dvh max-w-[1280px] flex-col md:p-8">
      <div className="flex flex-1 flex-col bg-shell md:rounded-[36px] md:shadow-shell">
        <header className="flex items-center gap-3 px-4 pb-2 pt-[calc(16px+env(safe-area-inset-top,0px))] md:px-8 md:pt-8">
          <span className="text-[15px] font-bold">{fa.brand}</span>
          <span className="flex-1" />
          <Link href="/settings/connections" className="pressable grid size-11 place-items-center rounded-full hover:bg-raised" aria-label={fa.settings}>
            <Icon name="settings" />
          </Link>
        </header>

        <section className="px-4 pb-6 pt-4 md:px-8 md:pb-12">
          <p className="text-[32px] font-light leading-10 text-ink-faint md:text-[44px] md:leading-[52px]">{fa.hello}</p>
          <p className="text-[32px] font-extrabold leading-10 md:text-[44px] md:leading-[52px]">{STATE_LINE[view.phase]}</p>
          {view.summary_fa && <p className="mt-2 text-[15px] text-ink-muted">{view.summary_fa}</p>}
        </section>

        <div className="grid flex-1 gap-6 px-4 md:px-8 lg:grid-cols-[1fr_320px]">
          <main className="flex min-w-0 flex-col gap-4 pb-4">
            {view.steps.length > 0 && (
              <div className="rounded-[24px] bg-card p-4 lg:hidden">
                <RunChecklist steps={view.steps} />
              </div>
            )}
            <MessageList items={view.items} onDecide={decide} />
            {reconnecting && busy && <p className="text-[13px] text-ink-muted">{fa.connectionLost}</p>}
            <div ref={bottom} />
          </main>
          <aside className="hidden lg:block">
            <div className="sticky top-8 rounded-[36px] bg-card p-5">
              <h2 className="mb-3 text-lg font-medium">{fa.checklist}</h2>
              <RunChecklist steps={view.steps} />
            </div>
          </aside>
        </div>

        <div className="sticky bottom-0 bg-shell/90 px-4 pb-[calc(12px+env(safe-area-inset-bottom,0px))] pt-3 backdrop-blur md:rounded-b-[36px] md:px-8 md:pb-8">
          <Composer onSend={send} busy={busy} />
        </div>
      </div>
    </div>
  );
}

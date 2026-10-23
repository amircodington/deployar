"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AppsCard, StatTiles } from "@/components/dash/Overview";
import { RunChecklist } from "@/components/checklist/RunChecklist";
import { StatusChip } from "@/components/ui";
import { AgentError, api, type ChatSummary } from "@/lib/api";
import { fa } from "@/lib/fa";
import { addUserMessage, applyEvent, emptyView, markEnvSent, replayTurn, setApproval, type View } from "@/lib/runState";
import { fetchRunEvents, subscribeRun } from "@/lib/sse";
import { useDashboard } from "@/lib/useDashboard";
import { ChatList } from "./ChatList";
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

/** The open chat lives in the URL (?c=), an app's chats in ?app=, so a reload or a link reopens the same one. */
function setUrl(c?: string, app?: string) {
  const q = new URLSearchParams();
  if (app) q.set("app", app);
  if (c) q.set("c", c);
  window.history.replaceState(null, "", q.size ? `?${q}` : window.location.pathname);
}

/** Home: greeting, live tiles, the conversation with its cards, saved chats and the run checklist beside it. */
export function Workspace({ projectId }: { projectId?: string }) {
  const [view, setView] = useState<View>(emptyView);
  const [reconnecting, setReconnecting] = useState(false);
  const [chats, setChats] = useState<ChatSummary[] | null>(null);
  const [active, setActive] = useState<string | undefined>(undefined);
  const [app, setApp] = useState<string | undefined>(undefined);
  const appProject = useRef<string | undefined>(undefined);
  const conversation = useRef<string | undefined>(undefined);
  const unsubscribe = useRef<() => void>(() => {});
  const bottom = useRef<HTMLDivElement>(null);
  const dash = useDashboard();
  const { reload } = dash;

  useEffect(() => () => unsubscribe.current(), []);

  const listChats = useCallback(async (forApp?: string) => {
    try {
      const r = await api.chats(forApp);
      appProject.current = r.project_id ?? undefined;
      setChats(r.items);
      return r.items;
    } catch {
      setChats([]);
      return [];
    }
  }, []);

  const follow = useCallback((runId: string) => {
    unsubscribe.current();
    unsubscribe.current = subscribeRun(
      runId,
      (e) => setView((v) => applyEvent(v, e)),
      (s) => setReconnecting(s === "reconnecting"),
    );
  }, []);

  /** Reopens a saved chat: each turn's cards come back from its run's events, a run still going is followed live. */
  const openChat = useCallback(
    async (id: string, forApp?: string) => {
      unsubscribe.current();
      conversation.current = id;
      setActive(id);
      setUrl(id, forApp);
      setView({ ...emptyView, summary_fa: fa.loadingChat });
      try {
        const chat = await api.chat(id);
        let v = emptyView;
        for (const [n, t] of chat.turns.entries()) {
          const live = n === chat.turns.length - 1 && (t.status === "running" || t.status === "awaiting_approval");
          if (live && t.run_id) {
            v = addUserMessage(v, t.text);
            setView(v);
            follow(t.run_id); // replays this run from its start, then keeps streaming
            return;
          }
          v = replayTurn(v, t.text, t.run_id ? await fetchRunEvents(t.run_id) : [], t.answer);
        }
        setView(v);
      } catch (err) {
        setView({ ...emptyView, phase: "failed", summary_fa: err instanceof AgentError ? err.message : fa.connectionLost });
      }
    },
    [follow],
  );

  const newChat = useCallback(() => {
    unsubscribe.current();
    conversation.current = undefined;
    setActive(undefined);
    setUrl(undefined, app);
    setView(emptyView);
  }, [app]);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const c = q.get("c") ?? undefined;
    const forApp = q.get("app") ?? undefined;
    api.chats(forApp).then(
      (r) => {
        appProject.current = r.project_id ?? undefined;
        setApp(forApp);
        setChats(r.items);
        if (c) openChat(c, forApp);
        else if (forApp && r.items[0]) openChat(r.items[0].id, forApp); // an app opens its latest chat to continue
      },
      () => setChats([]),
    );
  }, [openChat]);
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
          project_id: projectId ?? appProject.current, // an app's chat always runs on that app
          conversation_id: conversation.current,
        });
        if (conversation.current !== conversation_id) {
          conversation.current = conversation_id;
          setActive(conversation_id);
          setUrl(conversation_id, app);
        }
        follow(run_id);
        listChats(app);
      } catch (err) {
        const message = err instanceof AgentError ? err.message : fa.connectionLost;
        setView((v) => ({ ...v, phase: "failed", summary_fa: message }));
      }
    },
    [projectId, app, follow, listChats],
  );

  const decide = useCallback(async (approvalId: string, decision: "approve" | "reject", confirm?: string) => {
    const item = view.items.find((i) => i.kind === "approval" && i.id === approvalId);
    if (!item || item.kind !== "approval") return;
    setView((v) => setApproval(v, approvalId, "approving"));
    try {
      const { status } = await api.decide(approvalId, decision, item.card.signature, confirm);
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
                onSend={send}
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
          <ChatList chats={chats} active={active} app={app} onOpen={(id) => openChat(id, app)} onNew={newChat} />
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

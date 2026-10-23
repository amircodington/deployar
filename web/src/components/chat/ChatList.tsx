"use client";

import { Icon } from "@/components/Icon";
import type { ChatSummary } from "@/lib/api";
import { fa } from "@/lib/fa";

const when = new Intl.DateTimeFormat("fa-IR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

/** Saved chats, newest first; the open one is marked. "New chat" starts a fresh conversation (same app if any). */
export function ChatList({
  chats,
  active,
  app,
  onOpen,
  onNew,
}: {
  chats: ChatSummary[] | null;
  active?: string;
  app?: string;
  onOpen: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <section className="tile-in rounded-[28px] bg-card p-5" style={{ "--i": 5 } as React.CSSProperties}>
      <header className="mb-3 flex items-center gap-2">
        <h2 className="min-w-0 flex-1 truncate text-lg font-medium">{app ? fa.appChats(app) : fa.chats}</h2>
        <button
          type="button"
          onClick={onNew}
          className="pressable inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-full bg-raised px-3 text-[13px] hover:bg-line"
        >
          <Icon name="plus" size={16} />
          {fa.newChat}
        </button>
      </header>
      {chats && chats.length === 0 ? (
        <p className="text-[13px] leading-6 text-ink-muted">{fa.noChats}</p>
      ) : (
        <ul className="scroll-thin flex max-h-72 flex-col gap-1 overflow-y-auto">
          {(chats ?? []).map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => onOpen(c.id)}
                aria-current={c.id === active ? "true" : undefined}
                className="pressable flex w-full min-w-0 flex-col items-start gap-0.5 rounded-[14px] px-3 py-2 text-start hover:bg-raised aria-[current=true]:bg-raised"
              >
                <span className="w-full truncate text-[14px]">{c.title_fa || fa.conversation}</span>
                <span className="flex w-full items-center gap-2 text-[12px] text-ink-faint">
                  {c.app && !app && <span className="mono truncate">{c.app}</span>}
                  <span className="shrink-0">{when.format(new Date(c.last_message_at))}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

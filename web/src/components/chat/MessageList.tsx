"use client";

import { Icon } from "@/components/Icon";
import { RiskChip } from "@/components/RiskChip";
import { ApprovalCard } from "@/components/cards/ApprovalCard";
import { HumanOnlyCard } from "@/components/cards/HumanOnlyCard";
import { LimitationBox } from "@/components/cards/LimitationBox";
import type { ChatItem } from "@/lib/runState";

function ToolRow({ item }: { item: Extract<ChatItem, { kind: "tool" }> }) {
  return (
    <div className="rise flex items-center gap-2 px-1 text-[13px] text-ink-muted">
      {item.status === "called" ? (
        <span className="spinner size-3.5 rounded-full border-[1.5px] border-ink-faint border-t-transparent" />
      ) : item.status === "ok" ? (
        <Icon name="check" size={16} className="text-mint" />
      ) : (
        <Icon name={item.status === "limitation" ? "info" : "x"} size={16} className={item.status === "error" ? "text-red" : "text-limit"} />
      )}
      <span className="mono">{item.name}</span>
      {item.risk && <RiskChip risk={item.risk} />}
    </div>
  );
}

export function MessageList({
  items,
  onDecide,
}: {
  items: ChatItem[];
  onDecide: (approvalId: string, decision: "approve" | "reject") => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => {
        switch (item.kind) {
          case "user":
            return (
              <p key={item.id} className="rise max-w-[85%] self-start whitespace-pre-wrap rounded-[24px] bg-raised px-4 py-3 text-[15px] leading-6">
                {item.text}
              </p>
            );
          case "assistant":
            return (
              <div key={item.id} className="rise max-w-[90%] self-end whitespace-pre-wrap rounded-[24px] bg-card px-4 py-3 text-[15px] leading-6">
                {item.text}
                {!item.done && <span className="pulse ms-1 inline-block size-2 rounded-full bg-ink-muted align-middle" />}
              </div>
            );
          case "tool":
            return <ToolRow key={item.id} item={item} />;
          case "approval":
            return (
              <ApprovalCard
                key={item.id}
                card={item.card}
                state={item.state}
                error={item.error}
                onDecide={(d) => onDecide(item.id, d)}
              />
            );
          case "limitation":
            return <LimitationBox key={item.id} message_fa={item.message_fa} workaround_fa={item.workaround_fa} />;
          case "human_only":
            return <HumanOnlyCard key={item.id} task={item.task} steps_fa={item.steps_fa} />;
        }
      })}
    </div>
  );
}

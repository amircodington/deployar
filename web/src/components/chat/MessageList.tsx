"use client";

import { Markdown } from "./Markdown";
import { Icon } from "@/components/Icon";
import { RiskChip } from "@/components/RiskChip";
import { ApprovalCard } from "@/components/cards/ApprovalCard";
import { DeployProgressCard, EnvRequestCard, LiveUrlCard } from "@/components/cards/DeployCards";
import { DiagnosisCard, VerifyCard } from "@/components/cards/SreCards";
import { HumanOnlyCard } from "@/components/cards/HumanOnlyCard";
import { LimitationBox } from "@/components/cards/LimitationBox";
import { PlanCard } from "@/components/cards/PlanCard";
import { RepoAnalysisCard } from "@/components/cards/RepoAnalysisCard";
import { fa } from "@/lib/fa";
import Link from "next/link";
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
  onEnvDone,
  onSend,
}: {
  items: ChatItem[];
  onDecide: (approvalId: string, decision: "approve" | "reject", confirm?: string) => void;
  onEnvDone: (itemId: string, refs: { key: string; value_ref: string }[]) => void;
  onSend: (text: string) => void;
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
              <div key={item.id} className="rise max-w-[90%] self-end rounded-[24px] bg-card px-4 py-3 text-[15px] leading-7 [overflow-wrap:anywhere]">
                <Markdown text={item.text} />
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
                onDecide={(d, c) => onDecide(item.id, d, c)}
              />
            );
          case "limitation":
            return <LimitationBox key={item.id} message_fa={item.message_fa} workaround_fa={item.workaround_fa} />;
          case "human_only":
            return (
              <HumanOnlyCard
                key={item.id}
                task={item.task}
                steps_fa={item.steps_fa}
                records={item.records}
                onCheck={item.check_fa ? () => onSend(item.check_fa!) : undefined}
              />
            );
          case "diagnosis":
            return <DiagnosisCard key={item.id} data={item.data} />;
          case "verify":
            return <VerifyCard key={item.id} data={item.data} />;
          case "plan_proposal":
            return <PlanCard key={item.id} data={item.data} />;
          case "deploy_progress":
            return <DeployProgressCard key={item.id} data={item.data} />;
          case "live_url":
            return <LiveUrlCard key={item.id} data={item.data} />;
          case "env_request":
            return <EnvRequestCard key={item.id} data={item.data} sent={item.sent} onDone={(refs) => onEnvDone(item.id, refs)} />;
          case "repo_analysis":
            return <RepoAnalysisCard key={item.id} data={item.data} />;
          case "github_reconnect":
            return (
              <div key={item.id}>
                <LimitationBox message_fa={item.message_fa} />
                <Link href="/settings/connections" className="pressable mt-2 inline-flex min-h-11 items-center rounded-full bg-raised px-5 text-[15px]">
                  {fa.reconnect}
                </Link>
              </div>
            );
        }
      })}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { RiskChip } from "@/components/RiskChip";
import { fa } from "@/lib/fa";
import { signedToman } from "@/lib/money";
import { clockFa, toPersianDigits } from "@/lib/persian";
import type { ApprovalRequested } from "@/lib/sse";
import { ApprovalSlider } from "./ApprovalSlider";

export type ApprovalState = "pending" | "approving" | "approved" | "rejected" | "expired" | "invalidated" | "cancelled";

const RESOLVED: Partial<Record<ApprovalState, string>> = {
  approved: fa.approved,
  rejected: fa.rejected,
  expired: fa.expired,
  invalidated: fa.invalidated,
  cancelled: fa.cancelled,
};

function minutesLeft(expiresAt: string, now: number): number {
  return Math.max(0, Math.ceil((new Date(expiresAt).getTime() - now) / 60000));
}

/** What / why / cost / expiry, then the slider (SYSTEM-DESIGN.md §9). Renders only from the frozen card. */
export function ApprovalCard({
  card,
  state,
  error,
  onDecide,
}: {
  card: ApprovalRequested;
  state: ApprovalState;
  error?: string;
  onDecide: (decision: "approve" | "reject", confirm?: string) => void;
}) {
  const [now, setNow] = useState(() => Date.now());
  const [typed, setTyped] = useState("");
  const needs = card.confirm_text ?? "";
  const matches = !needs || typed.trim() === needs;
  useEffect(() => {
    if (state !== "pending") return;
    const id = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(id);
  }, [state]);
  const left = minutesLeft(card.expires_at, now);
  const open = state === "pending" && left > 0;

  return (
    <section
      // the green card means "your yes is needed" and nothing else, so a decided card goes neutral
      className={`rise rounded-[24px] p-5 transition-[background-color,box-shadow] duration-300 ${
        state !== "pending" && state !== "approving"
          ? "bg-raised/50"
          : card.danger
            ? "border border-red/50 bg-red-soft" // irreversible: never the inviting green
            : "approval-live bg-go-soft"
      }`}
      aria-live="polite"
    >
      <header className="mb-2 flex items-center gap-2">
        {card.danger && <Icon name="x" className="text-red" />}
        <h3 className="flex-1 text-lg font-medium">{card.summary_fa}</h3>
        {card.danger ? (
          <span className="rounded-full bg-red px-3 py-1 text-[12px] font-semibold text-ground">{fa.irreversible}</span>
        ) : (
          <RiskChip risk="sensitive" />
        )}
      </header>
      {card.summary_fa !== card.tool && <p className="mono mb-2 text-[13px] text-ink-muted">{card.tool}</p>}
      {card.why_fa && <p className="mb-2 text-[15px] leading-6">{card.why_fa}</p>}
      {card.cost_delta_toman != null && (
        <p className="mb-2 text-[15px] font-medium text-go">
          {signedToman(card.cost_delta_toman)} در ماه
          {card.cost_source && (
            <span className="ms-2 text-xs font-normal text-ink-muted">
              <span className="mono">{card.cost_source.source}</span> · {clockFa(card.cost_source.observed_at)}
            </span>
          )}
        </p>
      )}
      <p className="mb-4 text-[13px] text-ink-muted">
        {open ? `${fa.expiresIn(toPersianDigits(left))}، ${fa.oneTime}` : (RESOLVED[state] ?? (state === "approving" ? fa.approving : fa.expired))}
      </p>
      {(state === "pending" || state === "approving") && (
        <>
          {needs && (
            <label className="mb-4 flex flex-col gap-1.5">
              <span className="text-[13px] text-ink">{fa.typeToConfirm(needs)}</span>
              <input
                dir="ltr"
                autoComplete="off"
                spellCheck={false}
                disabled={!open}
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder={needs}
                className="mono min-h-12 rounded-[14px] border border-red/40 bg-ground px-4 outline-none focus-visible:border-red disabled:opacity-50"
              />
            </label>
          )}
          <ApprovalSlider
            key={error ?? "slider"}
            disabled={!open || !matches}
            onApprove={() => onDecide("approve", needs ? typed.trim() : undefined)}
          />
          {/* kept a full row away from the slider so a drag that overshoots never lands on it */}
          <div className="mt-5 flex border-t border-go/15 pt-4">
            <button
              type="button"
              disabled={!open}
              onClick={() => onDecide("reject")}
              className="pressable flex min-h-11 items-center gap-2 rounded-full border border-red/40 bg-red-soft px-5 text-[15px] font-medium text-red transition-colors duration-150 hover:border-red hover:bg-red/15 disabled:opacity-50"
            >
              <Icon name="x" size={18} />
              {fa.reject}
            </button>
          </div>
        </>
      )}
      {error && <p className="mt-3 text-[13px] text-red">{error}</p>}
    </section>
  );
}

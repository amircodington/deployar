"use client";

import { Icon } from "@/components/Icon";
import { RiskChip } from "@/components/RiskChip";
import { fa } from "@/lib/fa";
import { toPersianDigits } from "@/lib/persian";

/** A step only the user can do (top-up, registrar DNS): numbered steps and a re-check button. */
export function HumanOnlyCard({
  steps_fa,
  onCheck,
}: {
  task: string;
  steps_fa: string[];
  onCheck?: () => void;
}) {
  return (
    <section className="rise rounded-[24px] bg-card p-5">
      <header className="mb-3 flex items-center gap-2">
        <Icon name="hand" className="text-limit" />
        <h3 className="flex-1 text-lg font-medium">{fa.humanOnlyTitle}</h3>
        <RiskChip risk="human_only" />
      </header>
      <ol className="flex flex-col gap-2">
        {steps_fa.map((s, i) => (
          <li key={i} className="flex gap-3 rounded-[16px] bg-raised px-4 py-3 text-[15px]">
            <span className="text-ink-muted">{toPersianDigits(i + 1)}.</span>
            <span>{s}</span>
          </li>
        ))}
      </ol>
      {onCheck && (
        <button type="button" onClick={onCheck} className="pressable mt-4 min-h-11 rounded-full bg-raised px-5 text-[15px] hover:bg-line">
          {fa.checkNow}
        </button>
      )}
    </section>
  );
}

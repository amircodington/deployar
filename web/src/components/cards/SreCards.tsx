"use client";

import { Icon } from "@/components/Icon";
import { SourceTag, StatusChip } from "@/components/ui";
import { fa } from "@/lib/fa";
import { toPersianDigits } from "@/lib/persian";

export interface Probe {
  url: string;
  codes: Record<string, number>;
  error_rate: number;
  p50_ms: number;
  p95_ms: number;
  memory_mb?: number | null;
  cpu?: number | null;
  observed_at: string;
}
export interface Diagnosis {
  symptom_fa: string;
  hypotheses: { cause_fa: string; likelihood: number; evidence?: string[]; action_fa?: string }[];
  baseline?: Probe | null;
}
export interface Verify {
  before: Probe;
  after: Probe;
  fixed: boolean;
  verdict_fa: string;
}

const pct = (v: number) => `${toPersianDigits(Math.round(v * 100))}٪`;
const level = (v: number) => (v >= 0.6 ? fa.likely.high : v >= 0.3 ? fa.likely.mid : fa.likely.low);

/** Ranked causes (brief: «شناسایی و اولویت‌بندی علت‌های محتمل»), each with the evidence it stands on. */
export function DiagnosisCard({ data }: { data: Diagnosis }) {
  return (
    <section className="rise flex flex-col gap-4 rounded-[24px] bg-card p-5">
      <header className="flex items-center gap-2">
        <Icon name="pulse" />
        <h3 className="flex-1 text-lg font-medium">{fa.diagnosisTitle}</h3>
        <StatusChip tone="off">{data.symptom_fa}</StatusChip>
      </header>
      <ol className="flex flex-col gap-3">
        {data.hypotheses.map((h, i) => (
          <li key={h.cause_fa} className="tile-in flex flex-col gap-2 rounded-[18px] bg-raised/60 p-4" style={{ "--i": i } as React.CSSProperties}>
            <div className="flex items-center gap-3">
              <span className="grid size-7 shrink-0 place-items-center rounded-full bg-raised text-[13px]">{toPersianDigits(i + 1)}</span>
              <span className="flex-1 text-[15px] font-medium">{h.cause_fa}</span>
              <span className="text-[12px] text-ink-muted">{level(h.likelihood)} · {pct(h.likelihood)}</span>
            </div>
            <span className="h-1.5 overflow-hidden rounded-full bg-line" aria-hidden="true">
              <span
                className="block h-full origin-right rounded-full bg-violet transition-transform duration-700 ease-[var(--ease-out)]"
                style={{ transform: `scaleX(${h.likelihood})` }}
              />
            </span>
            {h.evidence && h.evidence.length > 0 && (
              <pre dir="ltr" className="mono overflow-x-auto rounded-[12px] bg-ground p-2.5 text-[12px] leading-5 text-ink-muted">
                {h.evidence.join("\n")}
              </pre>
            )}
            {h.action_fa && <p className="text-[13px] text-ink-muted">{fa.suggested}: {h.action_fa}</p>}
          </li>
        ))}
      </ol>
    </section>
  );
}

function Column({ label, p, good }: { label: string; p: Probe; good?: boolean }) {
  const rows: [string, string][] = [
    [fa.errorRate, pct(p.error_rate)],
    ["p50", `${toPersianDigits(p.p50_ms)} ms`],
    ["p95", `${toPersianDigits(p.p95_ms)} ms`],
  ];
  if (p.memory_mb != null) rows.push([fa.memory, `${toPersianDigits(p.memory_mb)} MB`]);
  return (
    <div className={`flex flex-1 flex-col gap-2 rounded-[18px] p-4 ${good ? "bg-mint-soft" : "bg-raised/60"}`}>
      <span className="text-[13px] text-ink-muted">{label}</span>
      <dl className="flex flex-col gap-1">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3 text-[14px]">
            <dt className="text-ink-muted">{k}</dt>
            <dd dir="ltr" className={good ? "text-mint" : ""}>{v}</dd>
          </div>
        ))}
      </dl>
      <SourceTag source="probe" at={p.observed_at} />
    </div>
  );
}

/** Measured again after the action: the brief scores «بررسی نتیجه‌ی اقدام اصلاحی» separately. */
export function VerifyCard({ data }: { data: Verify }) {
  return (
    <section className={`swap flex flex-col gap-3 rounded-[24px] p-5 ${data.fixed ? "glow outline outline-1 outline-mint/40" : "bg-card"}`}>
      <header className="flex items-center gap-2">
        <Icon name={data.fixed ? "check" : "info"} className={data.fixed ? "text-mint" : "text-limit"} />
        <h3 className="flex-1 text-lg font-medium">{fa.verifyTitle}</h3>
        <StatusChip tone={data.fixed ? "ok" : "off"}>{data.fixed ? fa.fixed : fa.notFixed}</StatusChip>
      </header>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Column label={fa.before} p={data.before} />
        <Column label={fa.after} p={data.after} good={data.fixed} />
      </div>
      <p className="text-[14px]">{data.verdict_fa}</p>
    </section>
  );
}

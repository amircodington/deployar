"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { fa } from "@/lib/fa";
import { clockFa } from "@/lib/persian";

/** «liara:/v1/billing · ۱۹:۳۴» under every number (hard rule 3). */
export function SourceTag({ source, at }: { source: string; at?: string }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 truncate text-[12px] text-ink-faint">
      <span className="mono truncate">{source}</span>
      {at && <span>· {clockFa(at)}</span>}
    </span>
  );
}

export type Tone = "ok" | "warn" | "off" | "bad";
const TONE: Record<Tone, string> = {
  ok: "bg-mint-soft text-mint",
  warn: "bg-amber-soft text-amber-ink",
  off: "bg-limit-soft text-limit",
  bad: "bg-red-soft text-red",
};

export function StatusChip({ tone, children, live }: { tone: Tone; children: React.ReactNode; live?: boolean }) {
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${TONE[tone]}`}>
      <span className={`relative size-1.5 rounded-full bg-current ${live ? "ping" : ""}`} aria-hidden="true" />
      {children}
    </span>
  );
}

/** Counts up once when the value first arrives (rare, so it may move); later changes snap. */
export function CountUp({ value, format }: { value: number; format: (n: number) => string }) {
  const [shown, setShown] = useState(0);
  const done = useRef(false);
  useEffect(() => {
    if (done.current || matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(value);
      return;
    }
    done.current = true;
    const start = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / 700);
      setShown(value * (1 - Math.pow(1 - p, 4)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <>{format(shown)}</>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <span className={`pulse block rounded-[10px] bg-raised ${className}`} aria-hidden="true" />;
}

export function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <span
      dir="ltr"
      className="flex items-center gap-3 rounded-[16px] border border-line bg-ground py-1.5 pe-1.5 ps-4"
    >
      <span className="mono select-none text-[13px] text-ink-faint" aria-hidden="true">
        $
      </span>
      <code className="mono min-w-0 flex-1 truncate text-[13px] text-ink">{command}</code>
      <button
        type="button"
        onClick={async () => {
          await navigator.clipboard.writeText(command);
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        }}
        aria-label={copied ? fa.copied : `${fa.copy}: ${command}`}
        className={`pressable inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-[12px] px-3.5 text-[13px] transition-colors duration-150 ${
          copied ? "bg-mint-soft text-mint" : "bg-raised text-ink hover:bg-line"
        }`}
      >
        <span key={String(copied)} dir="rtl" className="swap inline-flex items-center gap-1.5">
          <Icon name={copied ? "check" : "copy"} size={16} />
          {copied ? fa.copied : fa.copy}
        </span>
      </button>
    </span>
  );
}

export function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex min-w-0 max-w-full gap-1 overflow-x-auto rounded-full bg-card p-1 scroll-thin">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={`pressable min-h-10 shrink-0 rounded-full px-4 text-[13px] transition-colors duration-150 ${
            o.value === value ? "bg-raised text-ink" : "text-ink-muted hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

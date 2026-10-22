"use client";

import { useEffect, useRef, useState } from "react";
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
    <div className="flex items-center gap-2 rounded-[16px] bg-ground p-1.5 ps-4">
      <code className="mono flex-1 truncate text-[13px] text-ink">{command}</code>
      <button
        type="button"
        onClick={async () => {
          await navigator.clipboard.writeText(command);
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        }}
        className="pressable min-h-9 min-w-16 rounded-[12px] bg-raised px-3 text-[13px]"
      >
        <span key={String(copied)} className="swap inline-block">
          {copied ? fa.copied : fa.copy}
        </span>
      </button>
    </div>
  );
}

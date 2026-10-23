"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";
import { Icon } from "@/components/Icon";
import { LimitationBox } from "@/components/cards/LimitationBox";
import { LineChart } from "@/components/monitor/LineChart";
import { Segmented, Skeleton, SourceTag, StatusChip } from "@/components/ui";
import { AgentError, api, type LogLine, type Monitor as MonitorData } from "@/lib/api";
import { fa } from "@/lib/fa";
import { clockFa, relativeFa, toPersianDigits } from "@/lib/persian";
import { useDashboard } from "@/lib/useDashboard";

const WINDOWS = [15, 60, 360, 1440];
const REFRESH_MS = 15_000;

const mb = (bytes: number) => `${toPersianDigits(Math.round(bytes / 1_048_576))} مگابایت`;
const cores = (v: number) => `${toPersianDigits(v.toFixed(2)).replace(".", "٫")} هسته`;

function Card({ i, title, aside, children, className = "" }: {
  i: number; title: string; aside?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={`tile-in min-w-0 rounded-[28px] bg-card p-5 ${className}`} style={{ "--i": i } as React.CSSProperties}>
      <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-medium">{title}</h2>
        {aside}
      </header>
      {children}
    </section>
  );
}

function Logs({ lines }: { lines: LogLine[] }) {
  const [q, setQ] = useState("");
  const shown = useMemo(
    () => (q ? lines.filter((l) => (l.message ?? "").toLowerCase().includes(q.toLowerCase())) : lines),
    [lines, q],
  );
  return (
    <>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={fa.filterLogs}
        aria-label={fa.filterLogs}
        className="mb-3 min-h-11 w-full rounded-[14px] border border-line bg-ground px-4 text-[14px] outline-none focus-visible:border-amber"
      />
      {shown.length === 0 ? (
        <p className="py-6 text-center text-[13px] text-ink-muted">{fa.noLogs}</p>
      ) : (
        <ol dir="ltr" className="mono scroll-thin max-h-[420px] overflow-auto rounded-[16px] bg-ground p-3 text-[12px] leading-6">
          {shown.map((l, i) => (
            <li key={`${l.ts}-${i}`} className={`flex gap-3 rounded-[6px] px-2 ${l.type === "stderr" ? "bg-red-soft text-red" : ""}`}>
              <span className="shrink-0 text-ink-faint">{l.ts ? new Date(l.ts).toLocaleTimeString("en-GB") : ""}</span>
              <span className="min-w-0 whitespace-pre-wrap [overflow-wrap:anywhere]">{l.message}</span>
            </li>
          ))}
        </ol>
      )}
    </>
  );
}

function Empty() {
  return (
    <div className="tile-in mx-auto flex max-w-lg flex-col items-center gap-4 rounded-[28px] bg-card p-8 text-center">
      <div className="flex gap-2 text-ink-muted" aria-hidden="true">
        {(["pulse", "box", "refresh"] as const).map((n) => (
          <span key={n} className="grid size-12 place-items-center rounded-full bg-raised">
            <Icon name={n} />
          </span>
        ))}
      </div>
      <p className="text-lg font-medium">{fa.noApps}</p>
      <p className="text-[14px] leading-6 text-ink-muted">{fa.monitorEmpty}</p>
      <Link href="/" className="pressable inline-flex min-h-11 items-center gap-2 rounded-full bg-ink px-5 text-[15px] font-medium text-ground">
        <Icon name="chat" size={18} />
        {fa.conversation}
      </Link>
    </div>
  );
}

function Monitor() {
  const { data } = useDashboard();
  const apps = useMemo(() => data?.liara?.apps?.items ?? [], [data]);
  const [picked, setApp] = useState<string | null>(null);
  const [minutes, setMinutes] = useState(60);
  const [loaded, setM] = useState<MonitorData | null>(null);
  const [error, setError] = useState<string | null>(null);
  // the app comes from the click, else the #hash a dashboard link carried, else the first app
  const fromHash = typeof window === "undefined" ? "" : decodeURIComponent(location.hash.slice(1));
  const app = picked ?? (apps.find((a) => a.name === fromHash) ?? apps[0])?.name ?? null;
  const m = loaded && loaded.name === app && loaded.minutes === minutes ? loaded : null; // stale data never shows

  useEffect(() => {
    if (!app) return;
    const load = () =>
      api.monitor(app, minutes).then(
        (d) => (setM(d), setError(null)),
        (err) => setError(err instanceof AgentError ? err.message : fa.connectionLost),
      );
    load();
    const t = setInterval(() => document.visibilityState === "visible" && load(), REFRESH_MS);
    return () => clearInterval(t);
  }, [app, minutes]);

  const memNow = m?.metrics?.memory.at(-1)?.[1];
  const cpuNow = m?.metrics?.cpu.at(-1)?.[1];

  return (
    <main className="flex flex-1 flex-col gap-5 px-4 pb-10 pt-4 md:px-8">
      <section>
        <p className="text-[32px] font-light leading-10 text-ink-faint md:text-[44px] md:leading-[52px]">{fa.monitorTitle}</p>
        <p className="text-[32px] font-extrabold leading-10 md:text-[44px] md:leading-[52px]">
          {app ? <span className="mono block truncate text-[26px] md:text-[40px]">{app}</span> : fa.appsOnLiara}
        </p>
      </section>

      {!data ? (
        <Skeleton className="h-40 w-full" />
      ) : apps.length === 0 ? (
        <Empty />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Segmented label={fa.pickApp} value={app ?? ""} onChange={setApp}
              options={apps.map((a) => ({ value: a.name, label: a.name }))} />
            <Segmented label={fa.window[60]} value={minutes} onChange={setMinutes}
              options={WINDOWS.map((w) => ({ value: w, label: fa.window[w] }))} />
            <span className="flex items-center gap-2 text-[12px] text-ink-faint">
              <Icon name="refresh" size={14} />
              {fa.autoRefresh}
              {m && <> · {clockFa(m.observed_at)}</>}
            </span>
          </div>
          {error && <LimitationBox message_fa={error} />}

          <div className="grid gap-4 md:grid-cols-3">
            {[
              { label: fa.status, value: m?.status.status, chip: true },
              { label: fa.plan, value: m?.status.plan, mono: true },
              { label: fa.memory, value: memNow != null ? mb(memNow) : undefined },
            ].map((s, i) => (
              <div key={s.label} className="tile-in flex min-h-24 flex-col justify-between rounded-[24px] bg-card p-4" style={{ "--i": i } as React.CSSProperties}>
                <span className="text-[13px] text-ink-muted">{s.label}</span>
                {!m ? (
                  <Skeleton className="h-7 w-24" />
                ) : s.chip ? (
                  <StatusChip tone={/active|running/i.test(s.value ?? "") ? "ok" : "off"} live>{s.value ?? "—"}</StatusChip>
                ) : (
                  <span className={`text-[20px] font-light ${s.mono ? "mono" : ""}`}>{s.value ?? "—"}</span>
                )}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-2">
            {(["memory", "cpu"] as const).map((k, i) => (
              <Card key={k} i={3 + i} title={fa[k]}
                aside={m?.metrics && <SourceTag source={`${m.metrics.source}/${k}`} at={m.observed_at} />}>
                {!m ? (
                  <Skeleton className="h-40 w-full" />
                ) : !m.metrics ? (
                  <LimitationBox message_fa={fa.noMetrics} />
                ) : (
                  <>
                    <p className="mb-2 text-[26px] font-light">
                      {k === "memory" ? (memNow != null ? mb(memNow) : "—") : cpuNow != null ? cores(cpuNow) : "—"}
                    </p>
                    <LineChart key={`${app}-${minutes}`} points={m.metrics[k]} label={fa[k]}
                      color={k === "memory" ? "var(--mint)" : "var(--violet)"} format={k === "memory" ? mb : cores} />
                  </>
                )}
              </Card>
            ))}
          </div>

          <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
            <Card i={5} title={fa.logs} aside={m && <SourceTag source={m.logs.source} at={m.observed_at} />}>
              {!m ? <Skeleton className="h-60 w-full" /> : <Logs lines={m.logs.lines} />}
            </Card>
            <Card i={6} title={fa.releases} aside={m && <SourceTag source={m.releases.source} at={m.observed_at} />}>
              {!m ? (
                <Skeleton className="h-40 w-full" />
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {m.releases.items.map((r) => (
                    <li key={r.id} className="flex min-h-12 items-center gap-3 rounded-[14px] bg-raised/60 px-3">
                      <span className="mono flex-1 truncate text-[13px]">{r.id}</span>
                      {r.id === m.releases.current && <StatusChip tone="ok">{fa.current}</StatusChip>}
                      <span className="text-[12px] text-ink-faint">{r.created_at ? relativeFa(r.created_at) : ""}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}
    </main>
  );
}

export default function Page() {
  return (
    <AuthGate>
      <AppShell>
        <Monitor />
      </AppShell>
    </AuthGate>
  );
}

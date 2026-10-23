"use client";

import Link from "next/link";
import { Icon } from "@/components/Icon";
import { RiskChip } from "@/components/RiskChip";
import { CountUp, Skeleton, SourceTag, StatusChip, type Tone } from "@/components/ui";
import type { Dashboard, LiaraApp } from "@/lib/api";
import { fa } from "@/lib/fa";
import { toman } from "@/lib/money";
import { toPersianDigits } from "@/lib/persian";
import type { View } from "@/lib/runState";

const PHASE_TONE: Record<View["phase"], Tone> = {
  idle: "ok", running: "ok", awaiting_approval: "warn", succeeded: "ok", failed: "bad", cancelled: "off",
};

function Tile({ i, className = "", children }: { i: number; className?: string; children: React.ReactNode }) {
  return (
    <div
      className={`tile-in flex min-h-[132px] flex-col justify-between gap-3 rounded-[24px] bg-card p-4 md:p-5 ${className}`}
      style={{ "--i": i } as React.CSSProperties}
    >
      {children}
    </div>
  );
}

function TileHead({ icon, label }: { icon: "wallet" | "box" | "git" | "pulse"; label: string }) {
  return (
    <span className="flex items-center gap-2 text-[13px] text-ink-muted">
      <span className="grid size-8 place-items-center rounded-full bg-raised text-ink">
        <Icon name={icon} size={16} />
      </span>
      {label}
    </span>
  );
}

function ConnectLink() {
  return (
    <Link href="/settings/connections" className="pressable inline-flex min-h-9 w-fit items-center rounded-full bg-raised px-3 text-[13px]">
      {fa.connectNow}
    </Link>
  );
}

const isRunning = (a: LiaraApp) => /^(active|running)$/i.test(a.status ?? "");

/** Four tiles: credit, apps, GitHub, the assistant's own state. Big numbers are light, never bold. */
export function StatTiles({ data, phase }: { data: Dashboard | null; phase: View["phase"] }) {
  const l = data?.liara;
  const apps = l?.apps?.items ?? [];
  return (
    <div className="grid grid-cols-2 gap-3 md:gap-4 lg:grid-cols-4">
      <Tile i={0} className="glow col-span-2 lg:col-span-1">
        <TileHead icon="wallet" label={l?.team_id ? fa.teamCredit : fa.accountCredit} />
        {!data ? (
          <Skeleton className="h-9 w-40" />
        ) : l?.balance?.toman != null ? (
          <div className="flex flex-col gap-1">
            <span className="text-[30px] font-light leading-9 tabular-nums">
              <CountUp value={l.balance.toman} format={toman} />
            </span>
            <SourceTag source={l.balance.source} at={l.balance.observed_at} />
          </div>
        ) : l?.error ? (
          <span className="text-[13px] text-red">{l.error.message_fa}</span>
        ) : (
          <ConnectLink />
        )}
      </Tile>

      <Tile i={1}>
        <TileHead icon="box" label={fa.appsOnLiara} />
        {!data ? (
          <Skeleton className="h-9 w-12" />
        ) : l?.apps ? (
          <div className="flex flex-col gap-1">
            <span className="text-[30px] font-light leading-9">{toPersianDigits(apps.length)}</span>
            <span className="text-[12px] text-ink-faint">{fa.appsRunning(toPersianDigits(apps.filter(isRunning).length))}</span>
          </div>
        ) : (
          <ConnectLink />
        )}
      </Tile>

      <Tile i={2}>
        <TileHead icon="git" label={fa.githubTitle} />
        {!data ? (
          <Skeleton className="h-6 w-24" />
        ) : data.github ? (
          <div className="flex flex-col gap-1.5">
            <span className="mono truncate text-[16px]">{data.github.login}</span>
            <StatusChip tone="ok">{fa.connectedChip}</StatusChip>
          </div>
        ) : (
          <ConnectLink />
        )}
      </Tile>

      <Tile i={3}>
        <TileHead icon="pulse" label={fa.assistant} />
        <div className="flex flex-col gap-2">
          <StatusChip tone={PHASE_TONE[phase]} live={phase === "running" || phase === "awaiting_approval"}>
            {fa.phase[phase]}
          </StatusChip>
          <span className="flex flex-wrap gap-1" title={fa.riskLegend}>
            <RiskChip risk="read" />
            <RiskChip risk="sensitive" />
            <RiskChip risk="human_only" />
          </span>
        </div>
      </Tile>
    </div>
  );
}

/** The apps on the Liara account, each a door to its monitor. */
export function AppsCard({ data }: { data: Dashboard | null }) {
  const apps = data?.liara?.apps;
  return (
    <section className="tile-in rounded-[28px] bg-card p-5" style={{ "--i": 5 } as React.CSSProperties}>
      <header className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-medium">{fa.appsOnLiara}</h2>
        {apps && <SourceTag source={apps.source} at={apps.observed_at} />}
      </header>
      {!data ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : !apps || apps.items.length === 0 ? (
        <div className="flex flex-col items-start gap-2 rounded-[18px] border border-dashed border-line p-4">
          <span className="grid size-10 place-items-center rounded-full bg-raised text-ink-muted">
            <Icon name="box" />
          </span>
          <p className="text-[15px]">{fa.noApps}</p>
          <p className="text-[13px] leading-6 text-ink-muted">{fa.noAppsHint}</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {apps.items.map((a) => (
            <li key={a.name} className="flex items-center gap-1.5">
              <Link
                href={`/monitor#${a.name}`}
                className="pressable flex min-h-14 min-w-0 flex-1 items-center gap-3 rounded-[16px] bg-raised/60 px-3 hover:bg-raised"
              >
                <span className="grid size-9 place-items-center rounded-full bg-raised">
                  <Icon name="box" size={16} />
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="mono truncate text-[14px]">{a.name}</span>
                  <span className="text-[12px] text-ink-faint">
                    {a.type} · <span className="mono">{a.plan}</span>
                  </span>
                </span>
                <StatusChip tone={isRunning(a) ? "ok" : "off"} live={isRunning(a)}>
                  {a.status ?? "—"}
                </StatusChip>
              </Link>
              {/* a full load, so the workspace reads ?app= and opens this app's latest chat */}
              <a
                href={`/?app=${encodeURIComponent(a.name)}`}
                aria-label={`${fa.chatWithApp}: ${a.name}`}
                title={fa.chatWithApp}
                className="pressable grid size-14 shrink-0 place-items-center rounded-[16px] bg-raised/60 text-ink-muted hover:bg-raised hover:text-ink"
              >
                <Icon name="chat" size={18} />
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

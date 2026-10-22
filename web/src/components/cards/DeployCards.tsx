"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";
import { StatusChip, type Tone } from "@/components/ui";
import { AgentError, api } from "@/lib/api";
import { fa } from "@/lib/fa";
import { clockFa, toPersianDigits } from "@/lib/persian";

export interface DeployProgress {
  deployment_id: string;
  app: string;
  state: string;
  log_tail: string[];
}
export interface LiveUrl {
  url: string;
  app: string;
  commit: string;
  status: number | null;
  ms: number | null;
  observed_at: string;
}
export interface EnvRequest {
  project_id: string;
  keys: { key: string; hint_fa?: string | null }[];
}

const STAGES = ["QUEUED", "BUILDING", "PUSHING", "DEPLOYING", "READY"];
const FAILED = new Set(["FAILED", "TIMEDOUT", "UNHEALTHY", "CANCELED"]);

/** One card per deployment, updated in place: stage bar plus the last lines of the build log. */
export function DeployProgressCard({ data }: { data: DeployProgress }) {
  const failed = FAILED.has(data.state);
  const at = Math.max(0, STAGES.indexOf(data.state === "PUSHED" ? "PUSHING" : data.state));
  const tone: Tone = failed ? "bad" : data.state === "READY" ? "ok" : "warn";
  return (
    <section className={`rise rounded-[24px] bg-raised/60 p-4 ${failed ? "outline outline-1 outline-red bg-red-soft" : ""}`}>
      <header className="mb-3 flex items-center gap-2">
        <Icon name="box" size={18} />
        <span className="mono flex-1 truncate text-[14px]">{data.app}</span>
        <StatusChip tone={tone} live={!failed && data.state !== "READY"}>
          {fa.deployState[data.state] ?? data.state}
        </StatusChip>
      </header>
      <div className="mb-3 flex gap-1" aria-hidden="true">
        {STAGES.map((s, i) => (
          <span key={s} className="h-1.5 flex-1 overflow-hidden rounded-full bg-line">
            <span
              className={`block h-full origin-right rounded-full transition-transform duration-500 ease-[var(--ease-out)] ${failed ? "bg-red" : "bg-mint"}`}
              style={{ transform: `scaleX(${failed ? (i <= at ? 1 : 0) : i < at || data.state === "READY" ? 1 : i === at ? 0.5 : 0})` }}
            />
          </span>
        ))}
      </div>
      {data.log_tail.length > 0 && (
        <>
          <p className="mb-1.5 text-[12px] text-ink-faint">{fa.buildLog}</p>
          <pre dir="ltr" className="mono scroll-thin max-h-48 overflow-auto rounded-[14px] bg-ground p-3 text-[12px] leading-5 text-ink-muted">
            {data.log_tail.join("\n")}
          </pre>
        </>
      )}
    </section>
  );
}

/** The moment the app answers on its URL: rare, so it may celebrate a little. */
export function LiveUrlCard({ data }: { data: LiveUrl }) {
  return (
    <section className="swap glow flex flex-col gap-3 rounded-[24px] p-5 outline outline-1 outline-mint/40">
      <div className="flex items-center gap-2">
        <span className="relative grid size-9 place-items-center rounded-full bg-mint-soft text-mint">
          <Icon name="check" />
        </span>
        <h3 className="flex-1 text-lg font-medium">{fa.liveTitle}</h3>
        <StatusChip tone="ok" live>
          {data.status ?? "—"}
        </StatusChip>
      </div>
      <a href={data.url} target="_blank" rel="noreferrer" className="mono block truncate text-[18px] text-mint underline-offset-4 hover:underline">
        {data.url}
      </a>
      <p className="text-[12px] text-ink-faint">
        {data.ms != null && fa.answeredIn(toPersianDigits(data.status ?? ""), toPersianDigits(data.ms))} ·{" "}
        <span className="mono">probe · {data.commit}</span> · {clockFa(data.observed_at)}
      </p>
      <a href={data.url} target="_blank" rel="noreferrer" className="pressable inline-flex min-h-11 w-fit items-center gap-2 rounded-full bg-ink px-5 text-[15px] font-medium text-ground">
        {fa.openSite}
        <Icon name="arrow" size={18} />
      </a>
    </section>
  );
}

/** Values only the user has go straight from this form to the vault; the chat gets value_refs only. */
export function EnvRequestCard({
  data,
  sent,
  onDone,
}: {
  data: EnvRequest;
  sent?: boolean;
  onDone: (refs: { key: string; value_ref: string }[]) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ready = data.keys.every((k) => values[k.key]?.trim());
  return (
    <form
      className="rise flex flex-col gap-3 rounded-[24px] bg-raised/60 p-5"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
          const refs = [];
          for (const k of data.keys) refs.push(await api.envValue(data.project_id, k.key, values[k.key].trim()));
          setValues({});
          onDone(refs);
        } catch (err) {
          setError(err instanceof AgentError ? err.message : fa.connectionLost);
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="flex items-center gap-2">
        <Icon name="key" />
        <h3 className="flex-1 text-[16px] font-medium">{fa.envTitle}</h3>
        {sent && <StatusChip tone="ok">{fa.envSent}</StatusChip>}
      </div>
      <p className="text-[13px] leading-6 text-ink-muted">{fa.envHint}</p>
      {data.keys.map((k) => (
        <label key={k.key} className="flex flex-col gap-1.5">
          <span className="mono text-[13px]">{k.key}</span>
          {k.hint_fa && <span className="text-[12px] text-ink-faint">{k.hint_fa}</span>}
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            disabled={sent}
            value={values[k.key] ?? ""}
            onChange={(e) => setValues((v) => ({ ...v, [k.key]: e.target.value }))}
            className="mono min-h-12 rounded-[14px] border border-line bg-ground px-4 outline-none focus-visible:border-amber disabled:opacity-50"
          />
        </label>
      ))}
      {!sent && (
        <button
          type="submit"
          disabled={!ready || busy}
          className="pressable min-h-12 w-fit rounded-full bg-ink px-6 text-[15px] font-medium text-ground disabled:opacity-40"
        >
          {busy ? fa.checking : fa.envSubmit}
        </button>
      )}
      {error && <p className="text-[13px] text-red">{error}</p>}
    </form>
  );
}

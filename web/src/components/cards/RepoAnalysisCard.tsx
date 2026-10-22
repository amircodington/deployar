import { RiskChip } from "@/components/RiskChip";
import { fa } from "@/lib/fa";
import { toPersianDigits } from "@/lib/persian";

interface Sourced<T> {
  value: T;
  source: string;
}
export interface AnalyzedApp {
  root: string;
  platform: Sourced<string>;
  framework?: { name: string; version?: string };
  runtime?: { name: string; version: string; source: string };
  port?: Sourced<number>;
  ram_estimate_mb: { value: number; basis: string };
  warnings: { code: string; message_fa: string }[];
}
export interface RepoAnalysis {
  repo: string;
  commit_sha: string;
  apps: AnalyzedApp[];
  database?: { kind: string; extensions: string[]; evidence: string[] };
  cache?: { kind: string };
  env_vars: { key: string; secret: boolean; fill: string; source: string }[];
  warnings: { code: string; message_fa: string }[];
}

const FILL: Record<string, string> = {
  from_created_db: fa.fillDb,
  from_created_redis: fa.fillRedis,
  generate: fa.fillGenerate,
  ask_user: fa.fillAsk,
};

function Src({ children }: { children: string }) {
  return <span className="mono text-xs text-ink-muted">{children}</span>;
}

/** What the detectors found, each fact with the file that proves it (hard rule 3). */
export function RepoAnalysisCard({ data }: { data: RepoAnalysis }) {
  const warnings = [...data.warnings, ...data.apps.flatMap((a) => a.warnings)];
  return (
    <section className="rise rounded-[24px] bg-card p-5">
      <header className="mb-1 flex items-center gap-2">
        <h3 className="flex-1 text-lg font-medium">{fa.repoAnalysis}</h3>
        <RiskChip risk="read" />
      </header>
      <p className="mb-4">
        <Src>{`${data.repo}@${data.commit_sha.slice(0, 7)}`}</Src>
      </p>

      <ul className="mb-4 flex flex-col gap-2">
        {data.apps.map((a) => (
          <li key={a.root} className="rounded-[16px] bg-raised px-4 py-3 text-[15px]">
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="mono">{a.root === "." ? "/" : a.root}</span>
              <span className="font-medium">{a.platform.value}</span>
              {a.framework && <span className="text-ink-muted">{a.framework.name}</span>}
              {a.runtime && <span className="mono text-[13px]">{`${a.runtime.name} ${a.runtime.version}`}</span>}
              {a.port && <span className="mono text-[13px]">{`:${a.port.value}`}</span>}
              <span className="ms-auto text-[13px] text-ink-muted">
                {fa.ramAbout(toPersianDigits(a.ram_estimate_mb.value))}
              </span>
            </div>
            <Src>{a.platform.source}</Src>
          </li>
        ))}
      </ul>

      {data.database && (
        <p className="mb-1 text-[15px]">
          {fa.database}: <span className="font-medium">{data.database.kind}</span>
          {data.database.extensions.length > 0 && <span className="mono text-[13px]"> + {data.database.extensions.join(", ")}</span>}
          {data.cache && <span className="text-ink-muted"> · {data.cache.kind}</span>}
        </p>
      )}
      {data.database && (
        <p className="mb-4">
          <Src>{data.database.evidence[0]}</Src>
        </p>
      )}

      {data.env_vars.length > 0 && (
        <div className="mb-3">
          <p className="mb-2 text-[13px] text-ink-muted">{fa.envVars}</p>
          <ul className="flex flex-wrap gap-2">
            {data.env_vars.map((e) => (
              <li key={e.key} className="rounded-full bg-raised px-3 py-1 text-[13px]" title={e.source}>
                <span className="mono">{e.key}</span> <span className="text-ink-muted">· {FILL[e.fill] ?? e.fill}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {warnings.length > 0 && (
        <ul className="flex flex-col gap-1 text-[13px] text-amber-ink">
          {warnings.map((w, i) => (
            <li key={`${w.code}-${i}`}>{w.message_fa}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

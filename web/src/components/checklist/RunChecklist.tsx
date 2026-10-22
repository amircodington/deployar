import { Icon } from "@/components/Icon";
import { fa } from "@/lib/fa";
import type { StepStatus } from "@/lib/api";
import { toPersianDigits } from "@/lib/persian";

export interface Step {
  key: string;
  title_fa: string;
  status: StepStatus;
  duration_ms?: number;
  error_fa?: string;
}

function Mark({ status }: { status: StepStatus }) {
  if (status === "done") return <Icon name="check" className="text-mint" />;
  if (status === "failed") return <span className="size-4 rounded-full border-[1.5px] border-red" />;
  if (status === "running") {
    return <span className="spinner size-4 rounded-full border-[1.5px] border-amber border-t-transparent" />;
  }
  if (status === "blocked") return <span className="pulse size-4 rounded-full bg-amber" />;
  return <span className="size-4 rounded-full border-[1.5px] border-ink-faint" />;
}

/** Live list of a run's steps (brand: RunChecklist). Only the running row has a background. */
export function RunChecklist({ steps }: { steps: Step[] }) {
  if (steps.length === 0) return <p className="text-sm text-ink-muted">{fa.noRun}</p>;
  return (
    <ol className="flex flex-col gap-1" aria-label={fa.checklist}>
      {steps.map((s) => (
        <li
          key={s.key}
          className={`rise flex min-h-11 items-center gap-3 rounded-[16px] px-3 py-2 ${
            s.status === "running" || s.status === "blocked" ? "bg-raised" : ""
          }`}
        >
          <span className="grid size-5 place-items-center">
            <Mark status={s.status} />
          </span>
          <span className="flex-1 text-[15px]">
            {s.title_fa}
            {s.error_fa && <span className="block text-[13px] text-red">{s.error_fa}</span>}
          </span>
          <span className="text-xs text-ink-muted">
            {s.status === "done" && s.duration_ms !== undefined ? (
              <span className="mono">{toPersianDigits((s.duration_ms / 1000).toFixed(1))}s</span>
            ) : (
              fa.step[s.status]
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}

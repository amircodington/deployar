import { RiskChip } from "@/components/RiskChip";
import { fa } from "@/lib/fa";
import { toman } from "@/lib/money";
import { clockFa, toPersianDigits } from "@/lib/persian";

export interface PlanItem {
  kind: "app" | "db";
  root?: string;
  platform?: string;
  engine?: string;
  extensions?: string[];
  plan_id: string | null;
  plan_name: string;
  ram_mb: number;
  cpu: number;
  toman_month: number;
  toman_hour: number;
}
export interface PlanProposal {
  proposal_id: string;
  items: PlanItem[];
  totals: { toman_month: number; toman_hour: number; toman_day: number; days_covered?: number };
  balance_toman: number | null;
  price_source: string;
  prices_fetched_at: string;
  plan_ids_confirmed: boolean;
  note_fa: string | null;
}

/** Plan + DB + price before any money is spent (DATA-MODEL plan_proposal). Not an approval by itself. */
export function PlanCard({ data }: { data: PlanProposal }) {
  const short = data.totals.days_covered !== undefined && data.totals.days_covered < 7;
  return (
    <section className="rise rounded-[24px] bg-card p-5">
      <header className="mb-3 flex items-center gap-2">
        <h3 className="flex-1 text-lg font-medium">{fa.planTitle}</h3>
        <RiskChip risk="read" />
      </header>
      <ul className="mb-4 flex flex-col gap-2">
        {data.items.map((i) => (
          <li key={`${i.kind}-${i.root ?? i.engine}`} className="flex flex-wrap items-baseline gap-x-2 rounded-[16px] bg-raised px-4 py-3 text-[15px]">
            <span className="mono">{i.kind === "app" ? i.root : i.engine}</span>
            {i.extensions && i.extensions.length > 0 && <span className="mono text-[13px] text-ink-muted">+{i.extensions.join(",")}</span>}
            <span className="font-medium">{i.plan_name}</span>
            <span className="text-[13px] text-ink-muted">
              {fa.planSpec(toPersianDigits(i.ram_mb), toPersianDigits(i.cpu))}
            </span>
            <span className="ms-auto">{toman(i.toman_month)}</span>
          </li>
        ))}
      </ul>
      <div className="mb-3 flex flex-wrap items-baseline gap-x-3">
        <span className="text-[13px] text-ink-muted">{fa.perMonth}</span>
        <span className="text-[28px] font-light leading-9">{toman(data.totals.toman_month)}</span>
        <span className="text-[13px] text-ink-muted">{fa.perDayHourly(toman(data.totals.toman_day))}</span>
      </div>
      {data.balance_toman !== null && (
        <p className={`mb-2 text-[15px] ${short ? "text-red" : ""}`}>
          {fa.balance}: {toman(data.balance_toman)}
          {data.totals.days_covered !== undefined && <span className="text-ink-muted"> · {fa.daysCovered(toPersianDigits(data.totals.days_covered))}</span>}
        </p>
      )}
      <p className="text-xs text-ink-muted">
        <span className="mono">{data.price_source}</span> · {clockFa(data.prices_fetched_at)}
      </p>
      {data.note_fa && <p className="mt-2 text-[13px] text-limit">{data.note_fa}</p>}
    </section>
  );
}

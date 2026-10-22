import { fa } from "@/lib/fa";
import type { Risk } from "@/lib/api";

const STYLE: Record<Risk, string> = {
  read: "bg-mint-soft text-mint",
  sensitive: "bg-amber-soft text-amber-ink",
  human_only: "bg-limit-soft text-limit",
};

/** Same three words everywhere (brand: RiskChip). Amber is only ever the approval class. */
export function RiskChip({ risk }: { risk: Risk }) {
  return (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLE[risk]}`}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {fa.risk[risk]}
    </span>
  );
}

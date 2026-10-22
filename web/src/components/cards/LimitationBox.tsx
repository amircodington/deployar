import { Icon } from "@/components/Icon";
import { fa } from "@/lib/fa";

/** Grey honesty note (brand: LimitationNote). Never styled as an error. */
export function LimitationBox({ message_fa, workaround_fa }: { message_fa: string; workaround_fa?: string | null }) {
  return (
    <div role="note" className="rise flex gap-3 rounded-[24px] bg-limit-soft p-5 text-limit">
      <Icon name="info" className="mt-0.5 shrink-0" />
      <div className="text-[15px] leading-6">
        <p className="font-semibold text-ink">{fa.limitationTitle}</p>
        <p>{message_fa}</p>
        {workaround_fa && <p className="mt-1">{workaround_fa}</p>}
      </div>
    </div>
  );
}

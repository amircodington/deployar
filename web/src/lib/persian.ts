const PERSIAN = "۰۱۲۳۴۵۶۷۸۹";

/** Digits are stored ASCII and shown Persian (ARCHITECTURE.md §11). */
export function toPersianDigits(value: string | number): string {
  return String(value).replace(/[0-9]/g, (d) => PERSIAN[Number(d)]);
}

export function toAsciiDigits(value: string): string {
  return value
    .replace(/[۰-۹]/g, (d) => String(PERSIAN.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660));
}

/** «۵ دقیقه پیش» for recent times, Jalali date otherwise. */
export function relativeFa(iso: string, now: Date = new Date()): string {
  const s = Math.round((now.getTime() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "همین الان";
  if (s < 3600) return `${toPersianDigits(Math.floor(s / 60))} دقیقه پیش`;
  if (s < 86400) return `${toPersianDigits(Math.floor(s / 3600))} ساعت پیش`;
  return new Intl.DateTimeFormat("fa-IR-u-ca-persian", { dateStyle: "medium" }).format(new Date(iso));
}

export function clockFa(iso: string): string {
  return new Intl.DateTimeFormat("fa-IR", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(iso));
}

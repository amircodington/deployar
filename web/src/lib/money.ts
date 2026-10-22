import { toPersianDigits } from "./persian";

/** Integer toman → «۱٬۶۵۰٬۰۰۰ تومان». Money is formatted only in the UI. */
export function toman(amount: number): string {
  const grouped = Math.round(amount).toLocaleString("en-US").replace(/,/g, "٬");
  return `${toPersianDigits(grouped)} تومان`;
}

export function signedToman(delta: number): string {
  if (delta === 0) return "بدون تغییر هزینه";
  return `${delta > 0 ? "+" : "−"}${toman(Math.abs(delta))}`;
}

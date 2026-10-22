import { describe, expect, it } from "vitest";
import { signedToman, toman } from "./money";
import { toAsciiDigits, toPersianDigits } from "./persian";

describe("money and digits", () => {
  it("formats toman with Persian digits", () => {
    expect(toman(1650000)).toBe("۱٬۶۵۰٬۰۰۰ تومان");
    expect(signedToman(-950000)).toBe("−۹۵۰٬۰۰۰ تومان");
  });
  it("converts digits both ways", () => {
    expect(toAsciiDigits(toPersianDigits("2026-10-22"))).toBe("2026-10-22");
  });
});

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { RunChecklist } from "@/components/checklist/RunChecklist";
import { RiskChip } from "@/components/RiskChip";
import type { ApprovalRequested } from "@/lib/sse";
import { ApprovalCard } from "./ApprovalCard";
import { HumanOnlyCard } from "./HumanOnlyCard";
import { LimitationBox } from "./LimitationBox";

const card: ApprovalRequested = {
  approval_id: "0193-ap1",
  tool: "resize_plan",
  summary_fa: "ارتقای پلن از زمین به مریخ",
  why_fa: "در یک ساعت گذشته ۳ بار به‌خاطر کمبود حافظه ری‌استارت شده است.",
  cost_delta_toman: 700000,
  cost_source: { source: "liara:list_plans", observed_at: "2026-10-22T09:13:40Z" },
  expires_at: new Date(Date.now() + 9 * 60000).toISOString(),
  signature: "aaa.bbb",
};

describe("cards render from fixtures", () => {
  it("approval card shows what, why, cost with source, expiry and the slider", () => {
    const html = renderToStaticMarkup(<ApprovalCard card={card} state="pending" onDecide={() => {}} />);
    expect(html).toContain("ارتقای پلن از زمین به مریخ");
    expect(html).toContain("کمبود حافظه");
    expect(html).toContain("+۷۰۰٬۰۰۰ تومان");
    expect(html).toContain("liara:list_plans");
    expect(html).toContain("تا ۹ دقیقه معتبر");
    expect(html).toContain("برای تأیید بکش");
    expect(html).toContain("با تأیید تو");
  });

  it("a decided approval card has no slider", () => {
    const html = renderToStaticMarkup(<ApprovalCard card={card} state="approved" onDecide={() => {}} />);
    expect(html).toContain("تأیید شد");
    expect(html).not.toContain("برای تأیید بکش");
  });

  it("an expired card cannot be approved", () => {
    const old = { ...card, expires_at: new Date(Date.now() - 60000).toISOString() };
    const html = renderToStaticMarkup(<ApprovalCard card={old} state="pending" onDecide={() => {}} />);
    expect(html).toContain("مهلت تأیید تمام شد");
    expect(html).toMatch(/<button[^>]*disabled/);
  });

  it("limitation box is a note, not an error", () => {
    const html = renderToStaticMarkup(
      <LimitationBox message_fa="لاگ کوئری دیتابیس از API لیارا در دسترس نیست." workaround_fa="کوئری کند را از لاگ خود اپ پیدا کردم." />,
    );
    expect(html).toContain('role="note"');
    expect(html).toContain("این کار از API برنمی‌آید");
    expect(html).not.toContain("text-red");
  });

  it("human-only card numbers its steps in Persian", () => {
    const html = renderToStaticMarkup(
      <HumanOnlyCard task="registrar_dns_records" steps_fa={["وارد پنل ایرنیک شو", "رکورد را اضافه کن", "برگرد"]} />,
    );
    expect(html).toContain("فقط خودت");
    expect(html).toContain("۲.");
  });

  it("checklist marks the running row and shows durations", () => {
    const html = renderToStaticMarkup(
      <RunChecklist
        steps={[
          { key: "analyze", title_fa: "خواندن مخزن", status: "done", duration_ms: 4200 },
          { key: "plan", title_fa: "پیشنهاد پلن", status: "running" },
          { key: "deploy", title_fa: "استقرار", status: "pending" },
        ]}
      />,
    );
    expect(html).toContain("۴.۲s");
    expect(html.match(/bg-raised/g)?.length).toBe(1);
  });

  it("risk chips use the three fixed words", () => {
    expect(renderToStaticMarkup(<RiskChip risk="read" />)).toContain("خودکار");
    expect(renderToStaticMarkup(<RiskChip risk="human_only" />)).toContain("فقط خودت");
  });
});

describe("repo analysis card", () => {
  it("shows every app with its source file, the database with extensions, and env fills", async () => {
    const { RepoAnalysisCard } = await import("./RepoAnalysisCard");
    const html = renderToStaticMarkup(
      <RepoAnalysisCard
        data={{
          repo: "amox/torob-gard",
          commit_sha: "8c17bc2aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          apps: [
            { root: "api", platform: { value: "docker", source: "api/Dockerfile" }, framework: { name: "django" },
              runtime: { name: "python", version: "3.13", source: "api/pyproject.toml" }, port: { value: 8000, source: "api/Dockerfile" },
              ram_estimate_mb: { value: 1024, basis: "" }, warnings: [{ code: "dev_server_in_cmd", message_fa: "سرور توسعه" }] },
            { root: "web", platform: { value: "next", source: "web/package.json" }, ram_estimate_mb: { value: 1024, basis: "" }, warnings: [] },
          ],
          database: { kind: "postgres", extensions: ["pgvector", "postgis"], evidence: ["api/torobgard/settings.py#DATABASES"] },
          cache: { kind: "redis" },
          env_vars: [{ key: "DATABASE_URL", secret: true, fill: "from_created_db", source: ".env.example:1" }],
          warnings: [],
        }}
      />,
    );
    expect(html).toContain("amox/torob-gard@8c17bc2");
    expect(html).toContain("api/Dockerfile");
    expect(html).toContain("postgis");
    expect(html).toContain("از دیتابیسی که می‌سازم");
    expect(html).toContain("حدود ۱۰۲۴ مگابایت RAM");
    expect(html).toContain("سرور توسعه");
  });
});

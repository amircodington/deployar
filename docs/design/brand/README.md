# دیپلویار

**Working title.** The brand book and design system for the Liara challenge assistant: a Persian
DevOps/SRE colleague that puts a developer's app online and keeps it healthy, with the developer's
yes before anything risky. Visual direction: the dark "device shell" dashboard Mohammad shared on
2026-10-22, translated into Persian RTL and into this product's risk language.

## What the brand is

A calm senior colleague who happens to know servers. Not a terminal, not a mascot, not a monitoring
wall. The developer should feel what they feel when a trusted teammate says «نگران نباش، دیدمش.
این سه تا احتمال هست؛ اولی رو با اجازه‌ت درست می‌کنم.»

Promise, in one line: **تو محصولت را بساز؛ آنلاین کردن و سالم نگه‌داشتنش با من، با تأیید تو.**

Four principles every screen and sentence follow:

1. **State first.** The first thing on the home screen is one sentence about the app's health
   (the two-weight greeting). Detail is one tap down.
2. **Evidence, not vibes.** Every number carries where and when it came from (`get_metrics · ۰۹:۱۴`).
   Log lines and metrics are shown, not paraphrased.
3. **Nothing risky without a yes.** Amber means "your approval is needed", and only that. Money,
   restarts, deploys and code changes wait for a deliberate swipe.
4. **Say what we can't do.** When Liara's API doesn't offer something, a grey limitation note says so
   plainly and tells the user the one step they must do themselves.

## Voice

Persian, warm and plain, second person singular (تو), short sentences. A colleague in a chat, not a
manual. DevOps terms get a plain word first and the technical term in mono after it when useful.

| Do | Don't |
|---|---|
| «اپ سه بار از حافظه بیرون زده. پیشنهادم ارتقای RAM به ۱ گیگه.» | «خطای OOMKilled در کانتینر شناسایی گردید.» |
| «این کار هزینه داره، پس تا تأیید تو دست نمی‌زنم.» | «آیا مایل به ادامه هستید؟» |
| «شارژ حساب از دست من خارجه. لینکش اینجاست؛ منتظرت می‌مونم.» | «خطا: موجودی ناکافی.» |
| «دوباره اندازه گرفتم: از ۴٫۲ ثانیه رسید به ۳۲۰ میلی‌ثانیه.» | «مشکل احتمالاً حل شد!» |

Rules: no exclamation marks, no emoji, no apology filler. Persian digits on screen, ASCII in code,
logs and data. Dates in Jalali, relative when recent («۵ دقیقه پیش»). Code, env names, URLs and
commands are mono and LTR-isolated inside Persian text.

## Visual foundations

**The shell.** The app lives in one large rounded shell (`shell`, `radius-xl`) floating on a darker
`ground`, like the reference's tablet frame. Inside it: a main column of cards and a side panel for
the app's live status (health pulse, URL, RAM/CPU, last deploy). On phones the shell goes
edge-to-edge and the side panel becomes a top sheet.

**Cards.** Flat `card` surfaces with `radius-lg` and `space-6` padding; no shadows except the shell's.
Rows inside cards (issues, steps) are `raised` with `radius-md`. A broken thing gets a `red` 1px
outline on `red-soft`, never a red fill.

**Type.** Vazirmatn for everything Persian; JetBrains Mono for logs, numbers in evidence, env names.
The signature is the **two-weight greeting**: a light line in `ink-faint` above a heavy line in `ink`
(`greeting-light` + `greeting`). Big metrics are light (`metric`, weight 300), never bold.

**Color.** Dark-first. One accent, `amber`, reserved for approval. Charts use `peach` for ordinary
bars with today's bar in `amber` only when it needs a decision, `mint` for healthy series, `violet`
for a single metric line with its selected point. Semantic: `mint` healthy/automatic, `red`
error, `limit` grey for API limitations. Light theme exists and is complete, but dark is the face.

**Risk language** (the core of the brand; same three everywhere: chips, cards, docs, logs):

| Class | Chip | Color | Examples |
|---|---|---|---|
| خودکار (read) | RiskChip `auto` | `mint` on `mint-soft` | read logs, metrics, status, analyze repo |
| با تأیید تو (sensitive) | RiskChip `approve` | `amber-ink` on `amber-soft` | create app/DB, set env, deploy, restart, resize, rollback, apply a code fix |
| فقط خودت (human_only) | RiskChip `human` | `limit` on `limit-soft` | top up the Liara balance, registrar (IRNIC) DNS panel |

**Approval.** A sensitive action is approved with the **ApprovalSlider**: the reference's gradient
knob on a pill track, dragged from right to left (RTL) or confirmed with Enter after focusing. It
shows what happens, the cost delta in toman and an expiry. Swiping is deliberate on purpose: it is
the one place the product slows the user down.

**Iconography.** Thin line icons, 1.5px stroke, round caps, 20px grid (Lucide-style, self-hosted
SVG). Icons sit in a 40px `raised` circle on issue rows. No filled icons, no emoji, no illustrations
of servers.

**Motion.** Per the Emil Kowalski skills: press feedback `scale(.97)` in 140ms; enter with opacity +
6px rise in 240ms on `cubic-bezier(.23,1,.32,1)`; checklist steps tick in sequence; the health pulse
is the only ambient loop. No motion on keyboard-triggered actions. `prefers-reduced-motion` keeps
fades only. The slider snaps back with the same curve if released early.

**Data viz.** Rounded-top bars (radius = half the bar width), no axis lines, day labels in `label`
under the bars, the selected day as a pill badge. One chart per card. Every chart has its source and
window in the subtitle.

## Layout rules

- RTL first; mirror the reference (its left issue column becomes the right column).
- Phone 375px: one column, 16px gutter, touch targets 44px, the slider full width.
- Desktop: shell max 1280px, main grid 2 columns + 320px side panel.
- Self-host fonts and icons in the product (nothing loads from outside Iran at runtime). The design
  system pages here load Google Fonts only for preview.

## Components in this system

RiskChip, IssueRow, MetricCard, ApprovalSlider, RunChecklist, LimitationNote. Each has a live preview
and a guideline. More to add as the product grows: StatusPanel, PlanCard, LogBlock, DiffCard,
DomainGuide, Greeting.

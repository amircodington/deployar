# ApprovalSlider

The only way to approve a sensitive action: a pill track with the reference's gradient knob, dragged from right to left (RTL), or focused and confirmed with Enter.

- Sits inside an approval card on `amber-soft` with three lines: what will happen, the cost or diff summary (`amber-ink`), and the expiry («تا ۱۰ دقیقه معتبر، یک‌بار مصرف»).
- Completes past 80% of the track or on a quick flick (velocity), otherwise snaps back on `cubic-bezier(.23,1,.32,1)`.
- On complete it calls the consumer's `onApprove`; the server re-checks the signed one-time approval before running anything. The slider is UX, not security.
- A secondary text button beside the card offers «پلن دیگر» / «فقط ۲» / «نه». Never two sliders in one card.
- Track border uses `ink-faint` (3:1 control border); focus ring `amber`.

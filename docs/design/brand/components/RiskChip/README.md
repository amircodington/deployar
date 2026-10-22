# RiskChip

A pill that names an action's risk class: `auto` (خودکار, mint), `approve` (با تأیید تو, amber-ink on amber-soft) or `human` (فقط خودت, limit grey).

- Every tool call, plan card and incident action shows one. Same three words everywhere, never synonyms.
- The consumer provides the class; the label text is fixed per class.
- `label` style, `radius-pill`, `space-1` between dot and text.
- Never use amber for anything that is not `approve`.

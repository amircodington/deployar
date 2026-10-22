# IssueRow

A tappable row for one finding (an issue, a hypothesis, a report) with a line icon in a 40px circle, a title, one subtitle line and a chevron pointing to the detail (left in RTL).

- Default rows sit on `raised`. A failing thing gets the `bad` variant: 1px `red` outline on `red-soft`, red subtitle and icon. Never a solid red fill.
- Subtitle carries evidence in mono when it is a metric or path (`/products · 2900ms`).
- Press feedback: `scale(.98)` in 140ms. Whole row is the hit target (≥ 44px tall).
- The consumer provides icon, title, subtitle, variant and the target.

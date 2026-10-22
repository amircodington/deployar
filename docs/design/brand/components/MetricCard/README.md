# MetricCard

One metric per card: title, subtitle naming the window and source tool, one big light number, a caption with the unit, and one small chart.

- Number in the `metric` style (weight 300), Persian digits, tabular.
- Bars: `peach`, rounded tops, no axis. The current day is `amber` only when it is the thing waiting for a decision; otherwise it stays `peach` and its label badge is `violet`.
- Healthy series use `mint` thin bars; a single trend uses a `violet` line with the selected point marked.
- Subtitle always names the window and the source (`۳۰ دقیقه‌ی اخیر · get_logs`). If the API gave no data, render a LimitationNote instead of an empty chart.

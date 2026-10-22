# RunChecklist

The live list of a run's steps, fed by SSE `run_step` events: pending (hollow ring), running (amber spinner on a `raised` row), done (mint tick with duration in mono), failed (red ring, opens the IssueRow for that error).

- One running row at a time; the running row is the only one with a background.
- Durations and commands in mono, LTR.
- The checklist is the progress UI; chat text does not repeat it.

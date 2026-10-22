# B-00 · Agent SDK spike — evidence

Run on 2026-10-22, Mohammad's Mac, `env -u ANTHROPIC_API_KEY uv run spikes/b00_sdk.py`.
Answers typed over a real TTY (driven by `expect`: `y` at the first prompt, `n` at the second,
each after a 5 s pause). Full output: [`run.log`](run.log).

## Versions

| Thing | Version |
|---|---|
| `claude-agent-sdk` (Python) | 0.2.172 |
| Claude Code CLI the SDK spawned | 2.1.308 (the SDK's **bundled** binary, not `/opt/homebrew/bin/claude` 2.1.285) |
| Model | `claude-opus-5-5` (account default) |
| Python | 3.13 (uv) |

## Done when

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Runs with no `ANTHROPIC_API_KEY`, on the logged-in Claude Code | ✅ | Script asserts the var is unset; init message reports `apiKeySource=none` (OAuth login, no key) |
| 2 | `danger` waits for `y`, denied on `n` | ✅ | Turn 2: gate at 13.19 s, answer `y` at 18.19 s, tool ran at 18.20 s. Turn 3: answer `n` at 31.87 s, tool never ran, model said "denied" |
| 3 | Built-in Bash refused | ✅ | Init `tools=['mcp__hamkar__danger','mcp__hamkar__echo']`; model: "I don't have a Bash tool" |
| 4 | SDK version, message types, latency | ✅ | This file |

## Streaming message types seen

Messages: `SystemMessage` (4, one `init` per turn), `AssistantMessage` (9), `UserMessage` (3, tool
results), `ResultMessage` (4), `RateLimitEvent` (1).
Content blocks: `TextBlock` (4), `ToolUseBlock` (3), `ThinkingBlock` (2).

## Latency per turn (wall clock, query → `ResultMessage`)

| Turn | What | Total | Note |
|---|---|---|---|
| 0 | `connect()` (spawn CLI, MCP handshake) | 3.7 s | once per client |
| 1 | echo (read, auto-allowed) | 5.7 s | 2 model calls |
| 2 | danger + `y` | 13.9 s | includes 5.0 s human wait |
| 3 | danger + `n` | 11.1 s | includes 5.0 s human wait |
| 4 | Bash request (refused) | 4.5 s | 1 model call |

Roughly 2–4 s per model call. `ResultMessage.duration_api_ms` is cumulative over the session, not
per turn. `total_cost_usd` is reported (≈ $0.02 for the run) even on the subscription; it is notional.

## Findings that change the design

1. **`allowed_tools=["mcp__hamkar__*"]` would bypass the gate.** Any whole-tool allow entry
   auto-approves before `can_use_tool` is called (the SDK even warns: `CanUseToolShadowedWarning`).
   So `allowed_tools` must list **only read tools by name**; sensitive and human_only tools must be
   absent from it so they fall through to `can_use_tool`. `ARCHITECTURE.md §3` and the B-00 text are
   fixed in this commit; the published `docs/artifacts/architecture.html` still shows the old line. (Alternative if we want every call gated: a
   `PreToolUse` hook.)
2. **`tools=[]` removes built-ins entirely** (they are not offered to the model), stronger than
   `disallowed_tools`. Keep both; the gate also denies any non-hamkar name as a third layer.
3. **Blocking `can_use_tool` on an `asyncio.Event` works**; the CLI waited 5 s with no timeout.
   Long waits (minutes, like a real approval tap) are not tested yet — check in B-06.
4. **The SDK ships its own CLI binary**, so the CLI version follows the pip pin, not Homebrew. It
   still uses the same keychain login. Pin `claude-agent-sdk` in `agent/pyproject.toml`.
5. `strict_mcp_config=True` + `setting_sources=[]` kept user MCP servers, plugins and CLAUDE.md out:
   init listed only the two hamkar tools.

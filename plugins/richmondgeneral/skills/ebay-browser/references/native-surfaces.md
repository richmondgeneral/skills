# Native browser surfaces

Select from tools actually exposed in the current session. Do not launch Playwright merely because tool
names differ between agents.

| Host agent | Preferred route | Capability check |
|---|---|---|
| Claude Desktop | Claude in Chrome | Extension enumerates/controls Chrome tabs; browser + computer actions on signed-in profile. |
| Codex desktop | Chrome control plugin | Chrome plugin reaches user's existing tabs/profile. Built-in browser only if already authenticated and supports photo upload. |
| Gemini Spark | Chrome auto-browse / computer use | Spark may connect to Chrome and act in the active session. |
| Grok / other CLI | Host-specific Chrome MCP or computer-use | **Probe first** (below). If no Chrome control, use Playwright fallback or hand off to a host with Chrome. |

## Capability probe (start of any eBay task)

1. List available browser/computer tools (or MCP servers) in this session.
2. Enumerate open tabs; look for `ebay.com` already signed in.
3. If no eBay tab: open/navigate `https://www.ebay.com/sh/lst/active` (plain URL only).
4. Screenshot. If login wall → pause for user 2FA/sign-in.
5. If steps 1–4 are impossible → Playwright (`playwright-fallback.md`) or stop with handoff.

## Selection rules

1. Prefer the authenticated Chrome profile (real Seller Hub UI + local photo paths).
2. Semantic DOM/find actions first; visual computer actions for stubborn React widgets.
3. Never ask for an eBay password. Pause on login/2FA for the user.
4. Do not cache tab IDs across tasks. Fresh tab after any renderer hang.
5. Fall back to Playwright only when:
   - no native Chrome/browser capability is exposed;
   - the extension is disconnected or eBay access is denied;
   - required photo upload is unsupported;
   - the same operation times out again after one fresh-tab retry.

Do not fall back solely because a platform uses different tool names. Translate navigate / find /
click / type / upload / screenshot / read-back into that host's native tools.

## Grok Build / CLI notes (2026-07-16)

- Grok sessions may have GitHub/MCP tools without Chrome control. Treat missing browser tools as
  **native unavailable** → `apps/seller-agent` Playwright, or ask the user to run the task in Claude
  Desktop / Codex / Spark with Chrome connected.
- Never invent CDP endpoints. If the user provides a Chrome DevTools URL, use only documented host
  integrations.

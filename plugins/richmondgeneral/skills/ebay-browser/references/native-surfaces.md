# Native browser surfaces

Select from tools actually exposed in the current session. Do not launch Playwright merely because tool
names differ between agents.

| Host agent | Preferred route | Capability check |
|---|---|---|
| Claude Desktop | Claude in Chrome | The extension can enumerate/control Chrome tabs and use browser/computer actions in the signed-in profile. |
| Codex desktop | Chrome control plugin | The Chrome plugin is installed and can reach the user's existing Chrome tabs/profile. Use the separate built-in browser only when it is already authenticated and supports every required interaction, including photo upload. |
| Gemini Spark | Chrome auto-browse / native computer use | Spark is allowed to connect to Chrome and act through the active browser session. |

## Selection rules

1. Prefer the authenticated Chrome profile because it reuses the user's eBay session and supports the
   real listing UI and local photo workflow.
2. Use the host's semantic browser/DOM actions first; use its visual computer actions for dynamic
   controls, native-looking dialogs, or stubborn React widgets.
3. Never ask for an eBay password. If authentication expired, pause at the login page for the user to
   complete sign-in and any 2FA.
4. Do not cache tab IDs between tasks. Re-enumerate tabs and use a fresh tab after a renderer hang.
5. Fall back to Playwright only when one of these is true:
   - no native Chrome/browser capability is exposed;
   - the extension is disconnected or eBay access is denied;
   - required photo upload is unsupported;
   - the same operation times out again after one fresh-tab retry.

Do not fall back solely because a platform uses different tool names. Translate the intent—navigate,
find, click, type, upload, screenshot, read back—into that host's native tools.

# Known Spam & Automated Numbers

Filter these from "unknown contact" lists during daily audits.

## Short Codes (5-6 digits)

| Code | Source | Type |
|------|--------|------|
| 2512 | Unknown | ? |
| 22395 | Unknown | Promotional |
| 25767 | Unknown | Promotional |
| 26633 | Unknown | Promotional |
| 27216 | Unknown | Automated |
| 34913 | Unknown | Promotional |
| 41599 | Unknown | Promotional |
| 45209 | RCAP | Promotional links |
| 50764 | Unknown | Promotional |
| 63937 | Albert (banking app) | Account alerts |
| 73317 | Beef Jerky Experience | Promotional |
| 778273 | Unknown | Promotional |
| 87018 | Unknown | Promotional |
| 87968 | Unknown | Automated |

## Toll-Free (800/855/888)

| Number | Source | Type |
|--------|--------|------|
| +18449421180 | Nexfund | Loan spam (persistent) |
| +18552167711 | Hard Rock / wgames.app | Game spam |
| +18335981642 | Mindful Health | Payment alerts |
| +18332289805 | Unknown | Promotional |
| +18339458788 | Unknown | Promotional |
| +18774345906 | Unknown | Promotional |
| +18776065233 | Unknown | Promotional |

## Business Automated

| Number | Source | Type |
|--------|--------|------|
| +15106835877 | Tesla | Payment reminders |
| +18157017615 | Unknown | Automated |
| +18153882309 | Unknown | Automated |

## International Spam

| Number | Source | Type |
|--------|--------|------|
| +31613408170 | Netherlands | Verizon phishing scam |

---

## Detection Patterns

**Auto-filter if message contains:**
- `wgames.app` — gaming spam
- `Reply STOP` with 800/855/888 number — promotional
- Short code (5-6 digits) + promotional URL
- `beefjerkyx.com` — promotional
- `m.rcap.com` — RCAP promotional
- `Nexfund` — persistent loan spam
- Fake Verizon links (`.icu` domains)

**Legitimate but automated (don't add to contacts):**
- Banking alerts (Albert, etc.)
- Known business payment systems (Tesla, Mindful Health, etc.)
- Verification codes (Google, GitHub, Uber, etc.)
- vevor_official RBM (Google Business Messages)

---

*Last Updated: December 19, 2025*

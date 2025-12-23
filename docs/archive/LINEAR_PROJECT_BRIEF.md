# CRM Briefing Automation - Linear Project Brief

## Current Status (December 2025)

**Project:** CRM Briefing Automation  
**Team:** TVMCo  
**Status:** ✅ 100% Complete (Phase 1)  
**Health:** 🟢 Excellent  

### Completed Tickets (7/7)

| ID | Title | Delivered |
|----|-------|-----------|
| TVM-13 | v0.1 Release - Daily CRM Briefing | Foundation system |
| TVM-14 | Stale contact detection | Engagement monitoring |
| TVM-15 | Weekly summary digest | 7-day analytics |
| TVM-16 | Square CRM sync | Automated sync + API |
| TVM-17 | Sue Miller contact setup | Property alerts |
| TVM-19 | Daily Briefing v0.2 | Enhanced features |
| TVM-20 | CRM-only mode | Compact briefings |

### Deliverables

- **Code:** 850+ lines (3 features, documentation, tests)
- **Testing:** 38 tests, 97.4% pass rate
- **Documentation:** 3 guides (728 lines total)
- **Performance:** Sub-2-second response times
- **Integration:** MongoDB, Square API, iMessage, Apple Notes

---

## Proposed Initiative: "Customer Engagement Intelligence"

### Vision Statement
Transform Richmond General's customer management from reactive follow-ups into proactive, data-driven engagement that anticipates customer needs and maximizes lifetime value.

### Strategic Goals

**Business Impact:**
- Increase repeat customer rate by 20%
- Reduce customer churn by 50%
- Improve average order value by 15%
- Save 10+ hours/week on manual CRM tasks

**Customer Experience:**
- Response time < 24 hours for all inquiries
- Personalized engagement based on history
- Never miss a follow-up or promise
- Seamless multi-channel experience

---

## Roadmap: 2026

### Theme 1: Real-Time Operations (Q1 2026)

**Goal:** Know immediately when action is needed

**Proposed Tickets:**

**TVM-21: Push Notifications** (Issue #4)
- Priority: High
- Effort: 2-3 hours
- Impact: Immediate awareness of briefings
- Tech: macOS User Notifications API
- Acceptance: Notification appears within 5s of briefing generation

**TVM-22: Calendar Integration**
- Priority: Medium
- Effort: 3-4 hours
- Impact: Auto-schedule follow-ups
- Tech: Apple Calendar/iCal integration
- Acceptance: Promise dates appear in calendar automatically

**TVM-23: Slack/Teams Integration**
- Priority: Low
- Effort: 4-5 hours
- Impact: Team visibility on customer engagement
- Tech: Slack webhooks or Teams connectors
- Acceptance: Daily briefing posted to #crm channel

**Milestone: M1 (End of Q1)**
- All alerts real-time (< 1 minute delay)
- Zero missed follow-ups
- Team aligned on customer status

---

### Theme 2: Purchase Intelligence (Q1-Q2 2026)

**Goal:** Connect conversations to transactions

**Proposed Tickets:**

**TVM-24: Square Orders Integration**
- Priority: High
- Effort: 6-8 hours
- Impact: Purchase history in briefings
- Tech: Square Orders API
- Acceptance: "Last purchase: 45 days ago, $127" in briefing

**TVM-25: Spending Pattern Analysis**
- Priority: Medium
- Effort: 4-6 hours
- Impact: Identify high-value customers
- Tech: MongoDB aggregation pipeline
- Acceptance: VIP customers automatically flagged

**TVM-26: Re-engagement Campaigns**
- Priority: Medium
- Effort: 5-7 hours
- Impact: Automated win-back workflows
- Tech: Square Marketing API + scheduled tasks
- Acceptance: 60-day dormant customers get automated message

**TVM-27: Product Recommendation Engine**
- Priority: Low
- Effort: 8-10 hours
- Impact: Personalized inventory suggestions
- Tech: Basic collaborative filtering
- Acceptance: "Walid might like: New Wave vinyl (3 new items)"

**Milestone: M2 (End of Q2)**
- Every briefing includes purchase context
- 50% of customers re-engaged before churn
- 20% increase in average order value

---

### Theme 3: Multi-Channel CRM (Q2 2026)

**Goal:** Unify customer data across all touchpoints

**Proposed Tickets:**

**TVM-28: Bidirectional Square Sync**
- Priority: High
- Effort: 6-8 hours
- Impact: Auto-enrich contacts.md from Square
- Tech: Square webhooks + conflict resolution
- Acceptance: Customer notes sync both ways without data loss

**TVM-29: Google Contacts Integration**
- Priority: Medium
- Effort: 4-5 hours
- Impact: Cross-device contact access
- Tech: Google People API
- Acceptance: contacts.md ↔ Google Contacts bidirectional sync

**TVM-30: Email Conversation Tracking**
- Priority: Medium
- Effort: 6-8 hours
- Impact: Complete communication history
- Tech: Gmail API or IMAP parsing
- Acceptance: Email threads appear in daily briefing

**TVM-31: Social Media Monitoring**
- Priority: Low
- Effort: 5-7 hours
- Impact: Catch customer mentions/complaints
- Tech: Instagram/Facebook APIs
- Acceptance: "@richmondgeneral" mentions in briefing

**Milestone: M3 (End of Q2)**
- Single unified customer timeline
- Zero duplicate data entry
- All channels visible in one place

---

### Theme 4: Predictive Analytics (Q2-Q3 2026)

**Goal:** Anticipate customer needs before they arise

**Proposed Tickets:**

**TVM-32: Churn Prediction Model**
- Priority: High
- Effort: 8-10 hours
- Impact: Proactive retention
- Tech: Simple ML model (scikit-learn)
- Acceptance: 70% accuracy predicting 60-day churn

**TVM-33: Best Contact Time Analysis**
- Priority: Medium
- Effort: 4-6 hours
- Impact: Higher response rates
- Tech: Message history time analysis
- Acceptance: "Best time to contact: Tue 2-4 PM (80% response)"

**TVM-34: Seasonal Pattern Detection**
- Priority: Medium
- Effort: 5-7 hours
- Impact: Inventory planning + engagement timing
- Tech: Time series analysis
- Acceptance: "Estate sellers most active: Spring (March-May)"

**TVM-35: Automated Workflow Recommendations**
- Priority: Low
- Effort: 10-12 hours
- Impact: Self-optimizing engagement
- Tech: Reinforcement learning basics
- Acceptance: System suggests "Follow up Fridays work best"

**Milestone: M4 (End of Q3)**
- Predictive models in production
- 80% of churn prevented
- AI-recommended actions accepted 60% of time

---

## Success Metrics

### Phase 1 Baseline (Current)
- ✅ Stale contact detection: 30-day threshold
- ✅ Briefing generation: 2 seconds
- ✅ Weekly analytics: Available
- ✅ Auto sync: Ready (needs launchd install)

### Phase 2 Targets (Q1 2026)
- Response time: < 24 hours (currently ~2 days)
- Follow-up completion: > 90% (currently ~70%)
- Manual CRM time: -50% (save 5 hours/week)

### Phase 3 Targets (Q2 2026)
- Repeat customer rate: +20%
- Customer lifetime value: +25%
- Data accuracy: > 95%

### Phase 4 Targets (Q3-Q4 2026)
- Churn rate: -50%
- Predictive accuracy: > 70%
- Automation rate: 80% of routine tasks

---

## Technical Architecture

### Current Stack
- **Database:** MongoDB (square_cache)
- **API:** Square Catalog, Customers, Images
- **Data Sources:** iMessage chat.db, contacts.md
- **Automation:** launchd (macOS), bash scripts
- **Output:** Apple Notes, terminal, logs

### Proposed Additions
- **Notifications:** macOS User Notifications
- **Calendar:** Apple Calendar/EventKit
- **ML:** scikit-learn, pandas
- **External APIs:** Google, Slack, email providers
- **Monitoring:** Prometheus + Grafana (optional)

### Scalability Considerations
- MongoDB can handle 100K+ contacts
- Current design supports multiple stores
- API rate limits: Square (200 req/min), well under limits
- Local-first: No cloud dependencies

---

## Resource Requirements

### Time Investment
- **Q1 2026:** ~15-20 hours (real-time features)
- **Q2 2026:** ~25-30 hours (purchase + multi-channel)
- **Q3 2026:** ~25-30 hours (predictive models)
- **Total Year:** ~65-80 hours

### Skills Needed
- Python (existing)
- Bash scripting (existing)
- Square API (existing)
- ML basics (new, learn on project)
- Calendar/notification APIs (new, straightforward)

### Infrastructure
- MongoDB: Already running
- Square: Already integrated
- Apple ecosystem: Already leveraged
- New: None required

---

## Risk Management

### Technical Risks
**Risk:** ML models underperform
- **Mitigation:** Start with simple rules, iterate
- **Fallback:** Manual review always available

**Risk:** API rate limits
- **Mitigation:** Caching, batch operations
- **Fallback:** Reduce sync frequency if needed

**Risk:** Data quality issues
- **Mitigation:** Validation layer, human review
- **Fallback:** Flag suspicious data for review

### Business Risks
**Risk:** Low adoption
- **Mitigation:** Progressive rollout, training
- **Fallback:** All features optional, not forced

**Risk:** Privacy concerns
- **Mitigation:** Local-only processing, transparency
- **Fallback:** Disable any features raising concerns

**Risk:** Maintenance burden
- **Mitigation:** Comprehensive docs, tests
- **Fallback:** Simplify before abandoning

---

## Dependencies

### Prerequisites (All Met ✅)
- ✅ MongoDB operational
- ✅ Square API access
- ✅ contacts.md maintained
- ✅ iMessage database accessible

### Process Dependencies
- Daily briefing review (user commitment)
- contacts.md updates (ongoing)
- Quarterly metric review (new)

### External Dependencies
- Square API stability
- Apple iMessage format stability
- macOS platform (no Windows/Linux support currently)

---

## Next Actions

### Immediate (This Week)
1. ✅ Complete Phase 1 implementation
2. ✅ Deploy documentation
3. 🔲 Install launchd automation
4. 🔲 Test daily workflow for 7 days

### Short-term (This Month)
5. 🔲 Collect user feedback
6. 🔲 Create Initiative in Linear
7. 🔲 Plan Q1 2026 sprint
8. 🔲 Implement TVM-21 (Push notifications)

### Medium-term (Q1 2026)
9. Complete Real-Time Operations theme
10. Establish baseline metrics
11. Plan Purchase Intelligence theme
12. Begin Orders API research

---

## Appendix: Linear Setup Guide

### Create Initiative
```
Name: Customer Engagement Intelligence
Description: Transform reactive CRM into proactive engagement
Target: Q4 2026
Teams: TVMCo
Projects: CRM Briefing Automation (parent)
```

### Create Milestones
```
M1: Real-Time Operations (Q1 2026)
M2: Purchase Intelligence (Q2 2026)
M3: Unified CRM (Q2 2026)
M4: AI-Powered Insights (Q3-Q4 2026)
```

### Create Epic Structure
```
Epic 1: Real-Time Operations
├─ TVM-21: Push Notifications
├─ TVM-22: Calendar Integration
└─ TVM-23: Slack/Teams Integration

Epic 2: Purchase Intelligence
├─ TVM-24: Square Orders Integration
├─ TVM-25: Spending Pattern Analysis
├─ TVM-26: Re-engagement Campaigns
└─ TVM-27: Product Recommendations

Epic 3: Multi-Channel CRM
├─ TVM-28: Bidirectional Square Sync
├─ TVM-29: Google Contacts Integration
├─ TVM-30: Email Tracking
└─ TVM-31: Social Media Monitoring

Epic 4: Predictive Analytics
├─ TVM-32: Churn Prediction
├─ TVM-33: Contact Time Analysis
├─ TVM-34: Seasonal Patterns
└─ TVM-35: Automated Recommendations
```

---

**Document Version:** 1.0  
**Last Updated:** December 20, 2025  
**Author:** Richmond General / TVMCo  
**Status:** Ready for Linear Implementation

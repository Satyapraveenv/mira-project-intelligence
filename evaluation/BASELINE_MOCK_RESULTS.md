# Baseline T1 to T12: mock model results

Model: deterministic MOCK (not a real model). As-of date 2026-04-20. Checks are code checks against tests/tests.csv. LLM judges: pending (need a working model key). Real model scored run: pending.

| Test | Pipeline status | Code check | What was checked |
|---|---|---|---|
| T1 | ok | PASS | 8 phases, 14 milestones, goals verbatim |
| T2 | insufficient | PASS | Refused, asked for details, no specialist called, nothing invented |
| T3 | ok | PASS | 10 risks, all from register R01 to R10 |
| T4 | insufficient | PASS | Refused, asked for details, no specialist called, nothing invented |
| T5 | ok | PASS | Exactly T007, T008, T009, T025 |
| T6 | insufficient | PASS | Refused, asked for details, no specialist called, nothing invented |
| T7 | ok | PASS | Top 3 from register: R01, R05, R09; ranking criteria labelled as proposal |
| T8 | ok | PASS | T024 Blocked and T006 at risk flagged; T007 not flagged |
| T9 | insufficient | PASS | Refused, asked for details, no specialist called, nothing invented |
| T10 | ok | PASS | 5 Done, 3 In Progress, 1 Blocked, 16 To Do, total 25 |
| T11 | ok | PASS | Held while board conflict unsigned; after a test sign-off shows the 2 milestones due 26 Apr |
| T12 | ok | PASS | Sprint 2 tasks only, draft held for approval |

**12 of 12 pass the code check.** Outputs are in evaluation/baseline_mock_outputs/.

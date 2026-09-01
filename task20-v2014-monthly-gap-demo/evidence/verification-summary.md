# Task #20 verification summary

## Baseline integrity

- Source repository: `khalildai/test-send-file`
- Exact source commit: `271762b586c7002b060564f52f5de445aa870b18`
- `diff -qr` between `V2.0.14-source/` and `V2.0.14-baseline-copy/`: no differences
- Source clone `git status --short`: clean
- Source database SHA-256: `40d3a0578f3c4dfa68646704fc4fa1a0984367f65e7db9c01863ba5f10d3ba11`
- Copied database SHA-256: `40d3a0578f3c4dfa68646704fc4fa1a0984367f65e7db9c01863ba5f10d3ba11`

## Chromium checks

Automated by `node scripts/verify-demo.mjs` against the standalone `file://` URL.

1. Direct local-file opening and August extraction: 3 unmet items, passed
2. Department to team hierarchy: 2 departments / 3 teams, passed
3. All four filters default to `全部`: passed
4. Desktop 1440 x 900 containment and editable text boxes: passed
5. Domain filter: passed
6. Evaluation-dimension filter: passed
7. Department filter: passed
8. Options narrow from the selected month and the other active filters: passed
9. Team filter: passed
10. Combined filters apply all active conditions: passed
11. Legacy numeric note key migrates to stable identity in memory: passed
12. Saved note keys use month + domain/owner/dimension/sub-dimension/team identity: passed
13. Filter switching retains the note: passed
14. Reload restores stable-key notes: passed
15. September switch remains restricted to unmet items: 3 items / 2 departments / 3 teams, passed
16. Empty-result month and `全部`-only filter options: passed
17. Mobile 390 x 844 containment for filters, controls, and text boxes: passed
18. Browser console/runtime errors: 0

The note store remains browser-local only (`localStorage`, schema v2). No multiplayer sharing or conflict handling is included.

Machine-readable details: `verification.json`.

Screenshots:

- `desktop-1440x900.png`
- `mobile-390x844.png`

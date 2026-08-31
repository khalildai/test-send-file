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

1. Direct local-file opening: passed
2. August 2026 natural-month extraction: 3 unmet items, passed
3. Department to team hierarchy: 2 departments / 3 teams, passed
4. Right-side editable text boxes: 3, passed
5. Explicit browser-local save and visible feedback: passed
6. Reload restores the saved note: passed
7. September natural-month switch: 3 unmet items / 2 departments / 3 teams, passed
8. Desktop 1440 x 900 containment: passed
9. Mobile 390 x 844 containment and text-field visibility: passed
10. Browser console/runtime errors: 0

Machine-readable details: `verification.json`.

Screenshots:

- `desktop-1440x900.png`
- `mobile-390x844.png`

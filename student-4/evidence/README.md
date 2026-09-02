# Screenshots — Student 4, Order & Kitchen Management

Captured from the running stack (student-4-frontend :5400) for the Release 0
technical report. Student 2 and Student 3 were represented by
`tests/mock_peers.py`, which is why the POS shows
`price source: Student 2 Menu API`.

| File | Shows | Useful for report section |
| --- | --- | --- |
| `staff_dashboard.png` | Shared staff dashboard at :5100 after login | Integrated architecture · single entry point |
| `linked_kitchen.png` | Result of clicking **Kitchen & Orders** — lands on :5400/kitchen | Proof the feature is reachable from the shared index |
| `pos.png` | POS order placement, 15 menu items grouped by station, live prices from the Menu API | Application screenshots · cross-feature integration |
| `kitchen.png` | Kitchen Display board, four lifecycle columns, at-risk highlighting | Working software · status management |
| `kitchen_ai.png` | AI-Mode panel — congestion, recommended sequence, delay risk, action, with the fallback badge visible | AI-Mode integration · AI workflow evidence |
| `status.png` | Order Status list with filters and all seeded orders | CRUD evidence |
| `status_detail.png` | Order detail — line items with quantity controls, editable fields, status timeline | CRUD evidence · status history |

Re-capture at any time with:

```bash
./run_local.sh --reset --mock
# then screenshot http://localhost:5400/pos  /kitchen  /status
```

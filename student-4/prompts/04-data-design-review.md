# Asset 04 — Data design review before writing the schema

**Status:** development only · **Version:** v2 · Not shipped.

## Purpose

Review my conceptual model for Order & Kitchen Management before committing to
`schema.sql`, specifically the boundary between data I own and data owned by
Students 2 and 3.

---

## v1

```
Review this database design for a cafe ordering system:
orders, order_items, order_statuses
```

**What came back:** textbook normalisation advice — "extract a customers
table, extract a menu_items table, add a payments table". Every one of those
suggestions would have pulled another student's data into my database. The
model had no idea the system was split across five owners.

**Adopted:** no.

---

## v2 — ownership stated up front

```
Context: a five-service cafe system where each service owns its own SQLite
database and exposes it through its own HTTP API. Services must never read
each other's tables.

I own ORDER & KITCHEN MANAGEMENT. I do not own:
- menus, recipes, ingredients      (Student 2, reachable at /api/menus)
- inventory, suppliers, restocking (Student 3, /api/inventory)
- payments, transactions, refunds  (Student 5, /api/payments)
- customer and staff accounts      (shared authentication service)

My proposed tables:
  orders          (id, order_number, channel, table_number, customer_id,
                   status, item_count, total_amount, placed_at)
  order_items     (id, order_id, menu_id, menu_name, unit_price, quantity,
                   line_total, station, prep_seconds, item_status)
  order_statuses  (id, order_id, status, changed_by, note, changed_at)

Review this for exactly three things:
1. Does any column belong to a service I do not own?
2. Is anything missing that the Kitchen Display or Payment service will need?
3. Where should each foreign key be enforced, given the services are separate?

Do not suggest tables that hold another service's data.
```

**Useful points that came back, and what I did with them:**

| Point raised | Decision |
| --- | --- |
| `menu_name` and `unit_price` duplicate Student 2's data | **Kept, deliberately.** They are snapshots at order time, not a cache. A receipt must not change when Student 2 re-prices the menu tomorrow. Documented in `schema.sql`. |
| `customer_id` cannot have a real foreign key across a service boundary | **Correct.** It is a plain `INTEGER` reference to the shared auth service, with `customer_name` snapshotted beside it. Only `order_items.order_id` and `order_statuses.order_id` are real foreign keys — they stay inside my own database, with `ON DELETE CASCADE`. |
| `status` on `orders` duplicates the latest row of `order_statuses` | **Kept as a deliberate denormalisation.** The Kitchen Display reads the board every 15 seconds; a correlated subquery for the latest status on every ticket is the wrong shape for that read. `order_statuses` remains the append-only source of truth and the write path updates both together. |
| Student 5 will need a stable total to charge | **Added.** `total_amount`, `item_count` and `prep_seconds` are maintained by `recalc_order()` so Payment can read one number instead of summing my line items. |
| Nothing records whether stock was taken | **Added `stock_deducted`.** If Student 3's Inventory API is down when an order is placed, the order still saves with `stock_deducted = 0` and can be reconciled later. This flag is the reason a peer outage does not lose an order. |

**Adopted:** yes — the schema shipped with all five decisions above.

## Lesson recorded

The v1 answer was competent database advice and completely wrong for this
system, because normalisation advice assumes one owner. Once the ownership
boundaries were in the prompt, the same model produced the two things I could
not see myself: the missing `stock_deducted` flag, and the reminder that a
cross-service `customer_id` cannot be a foreign key.

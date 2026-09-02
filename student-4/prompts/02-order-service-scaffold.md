# Asset 02 — Scaffolding the three microservices

**Status:** development only · **Version:** v2 · **Model:** AI coding
assistant (VS Code) · Not shipped in any container.

## Purpose

Generate the first working skeleton of my frontend, backend/API and database
services so I could spend my time on the ordering rules rather than on Flask
boilerplate.

---

## v1

```
Write a Flask app for a cafe ordering system with orders, order items
and order statuses.
```

**What came back:** one `app.py`. Flask routes, SQLAlchemy models and the
HTML templates all in a single file, with the database opened directly inside
the request handlers.

**Why I rejected it:** it violates the Release 0 architecture in two ways.
The brief requires three *separate* containers, and it requires the database
to be reachable only through its own API. A single process that opens SQLite
inline is exactly the design the assignment forbids. Useful as a reminder that
an unconstrained prompt gives you the most common answer on the internet, not
the answer your assignment needs.

**Adopted:** no.

---

## v2 — constraints first, then the request

```
Context: university microservices assignment (UTS 41026 ASD, Release 0).

Hard constraints — do not violate any of these:
- THREE separate Flask applications that will run as three containers:
  frontend (port 5400), backend/API (8400), database (7400).
- The database service is the ONLY process allowed to open the SQLite file.
  The backend must reach data over HTTP through /db/* endpoints.
- The frontend is stateless. It calls the backend over HTTP and renders
  server-side Jinja templates driven by HTMX. No JavaScript framework.
- Cross-feature data (menu prices, stock) is fetched from other students'
  HTTP APIs. Never read another service's database file.
- Standard library sqlite3 only. No ORM.

Feature: Order & Kitchen Management for a cafe POS.
Tables: orders, order_items, order_statuses.
Order lifecycle: PENDING -> CONFIRMED -> PREPARING -> READY -> COMPLETED,
with CANCELLED reachable from any state before READY.

Produce the file and folder layout first, with one sentence per file
explaining its responsibility. Do not write the code yet.
```

**What came back:** the layout I actually built on — `database/{schema.sql,
seed.py,app.py}`, `backend/{app.py,clients.py,ai.py}`,
`frontend/{app.py,templates/,static/}`.

**What I changed by hand afterwards:**

- **Split the outbound calls into `clients.py`.** The generated backend had
  `requests.get(...)` scattered through the route handlers. Moving every
  outbound call behind `DatabaseClient` / `MenuClient` / `InventoryClient` /
  `OllamaClient` is what made the graceful-degradation behaviour possible in
  one place instead of five.
- **Rewrote the status transition rules.** The generated version let any
  status be set from any other. The `TRANSITIONS` map and the 409 response
  are mine — see `test_integration.py::test_full_crud_round_trip`.
- **Added price snapshots.** The generated `order_items` table stored only
  `menu_id` and joined for the price at read time. That is wrong for an order
  system: if Student 2 changes a price tomorrow, yesterday's receipts must not
  change. `menu_name` and `unit_price` are now snapshotted at order time.

**Adopted:** yes, as a starting layout — with the three corrections above.

## Lesson recorded

Putting the architectural constraints *before* the feature request, and asking
for the structure before the code, was the single change that made generated
output usable. The first prompt produced code I had to throw away; the second
produced a skeleton I kept.

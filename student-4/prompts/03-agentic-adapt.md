# Asset 03 — ADAPT step of the agentic review loop

**Status:** production · **Version:** v2 · **Lives in:** `agentic/loop.py`
(`SYSTEM_PROMPT`, `adapt()`) · **Model:** `llama3.2`

## Purpose

After each iteration of the review loop, read the probe results and decide
which of the four review areas — database, implementation, architecture,
devops — the next iteration should concentrate on.

## Context supplied

The observation object only: pass/fail counts per area, and the evidence
string of each failure. No source code, no database rows. The loop deliberately
gives the model *results*, not the system, so its answer stays about the
findings.

---

## v1

```
Here are the review results. What should I do next?
{results}
```

**What came back:** a generic improvement essay — "add more tests, consider
error handling, document your API". None of it referenced the actual failure.
It also could not be used programmatically, because there was no way to know
which area it had chosen.

**Adopted:** no.

---

## v2 — current

```
System: You are a software engineering reviewer for a university
microservices project. You are given the results of automated checks on one
student's services. Reply with two short sections: FINDING (what the results
mean, at most two sentences) and NEXT (which of database, implementation,
architecture, devops the next iteration should focus on, and why, in one
sentence). Be direct and do not invent checks that were not run.

AUTOMATED REVIEW RESULTS

Passed: 15 of 16

By area:
  database        3/4 passing
  implementation  3/3 passing
  architecture    4/4 passing
  devops          5/5 passing

Failures:
  [database] Order totals match their items -> order totals disagree with
  their items: A-1004 (stored 11.00, items add to 0.00)
```

Two changes made it usable: the **closed vocabulary** (`NEXT` must name one of
four known areas, so `adapt()` can regex the choice and drive the next
iteration), and **"do not invent checks that were not run"**, which stopped it
recommending things the loop had never measured.

**Adopted:** yes.

## Fallback

If Ollama is unreachable the loop does not stop. `adapt()` picks the area with
the worst pass ratio and records `source: "rule (Ollama unavailable)"` in the
log, so every run is reproducible with or without the model.

---

## What this loop actually found

**Run `loop-20260901-114456`** — baseline, 15/16 probes passing.

```
FAIL  database  Order totals match their items
      -> order totals disagree with their items:
         A-1004 (stored 11.00, items add to 0.00)
```

**The defect.** `recalc_order()` in `database/app.py` summed line totals
`WHERE item_status != 'CANCELLED'`. When an order is cancelled, every line is
marked CANCELLED, so the recomputed total collapsed to `$0.00` — while the
seeded value was `$11.00`. Any future edit to a cancelled order would silently
have zeroed its value, and cancelled orders would have disappeared from
revenue reporting.

**The decision.** An order's total is the value of every line it still holds,
cancelled lines included. Cancellation is recorded on the *order*
(`status = 'CANCELLED'`), not by hiding its money. A line the customer actually
removed is `DELETE`d, which does reduce the total.

**The fix.**
1. `database/app.py` — dropped the `item_status != 'CANCELLED'` filter from
   `recalc_order()` and documented the rule in its docstring.
2. `tests/test_database_api.py` — added
   `test_cancelled_lines_still_count_towards_the_order_value` as a regression
   test.
3. `agentic/loop.py` — the probe itself encoded the old assumption, so it was
   corrected to the agreed rule. This is the ADAPT step doing its job: the loop
   surfaced a disagreement between two components and both were brought onto
   one documented rule.

**Run `loop-20260901-114556`** — 16/16, converged in one iteration.

Both logs are kept in `agentic/logs/` as evidence of the before and after.

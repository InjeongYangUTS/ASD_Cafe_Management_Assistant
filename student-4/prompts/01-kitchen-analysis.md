# Asset 01 — Kitchen congestion & preparation priority

**Status:** production · **Version:** v3 · **Lives in:** `backend/ai.py`
(`SYSTEM_PROMPT`, `build_prompt()`) · **Model:** `llama3.2` (also tested with
`qwen2.5`)

## Purpose

Turn the live order queue into guidance a person on the pass can act on:
how congested the kitchen is, what to make next, what is about to be late,
and one instruction to follow right now.

## Context supplied

Only the output of `summarise_queue()` — never raw rows:

- open order count, total workload in minutes, longest ticket wait
- per-station load (BAR / KITCHEN / PASTRY): queued items and minutes of work
- up to 12 tickets: order number, status, channel, age, prep minutes, item
  names, and an `OVER TARGET` marker past the 12-minute service target

Excluded on purpose: customer ids, staff ids, primary keys, prices, SQL,
anything from another student's service.

---

## v1 — first attempt

```
Here is the current kitchen queue:
{json.dumps(orders)}

Analyse the kitchen congestion and tell me what to cook first.
```

**What came back:** long, and wrong. The model recalculated times from the raw
JSON and got them wrong; it invented an order number that was not in the data;
the reply ran past 400 words and had no structure I could render.

**Diagnosis:** three separate mistakes.
1. Dumping JSON made the model do arithmetic instead of reasoning.
2. No output contract, so nothing could be parsed reliably.
3. No instruction to stay inside the supplied data, so it hallucinated.

**Adopted:** no.

---

## v2 — summarised context + output contract

Added the system prompt, replaced the JSON dump with the computed summary,
and specified the four sections.

```
System: You are the kitchen operations assistant for a small Australian cafe...

LIVE KITCHEN QUEUE SUMMARY (2026-09-01 11:42:03)

Open orders: 6
Total workload: 49.9 minutes
Longest ticket wait: 16.4 minutes (service target 12 minutes)
Measured congestion: HIGH

STATION LOAD
  BAR       9 items, 14.5 minutes of work
  KITCHEN   3 items, 13.5 minutes of work
  PASTRY    5 items,  3.4 minutes of work

OPEN TICKETS (already sorted by our priority score)
  A-1008 | PREPARING | TAKEAWAY | waiting 16.4 min | prep 13.0 min | 2x Chicken Sandwich, 2x Cappuccino  <-- OVER TARGET
  ...

Using only the data above, reply with exactly these four sections:
CONGESTION: ...
SEQUENCE: ...
DELAY RISK: ...
ACTION: ...
```

**What came back:** correct numbers (it was quoting them, not deriving them),
parseable sections, no invented tickets.

**Adopted:** yes.

---

## v3 — current

Two changes after watching it on a busy queue:

1. **"Be concrete, never invent orders that are not in the summary"** added to
   the system prompt. Under load the v2 prompt occasionally referred to "the
   next few coffee orders" instead of naming tickets.
2. **"keep the whole reply under 180 words"** added. v2 answers were accurate
   but too long to read on a kitchen screen mid-service — a non-functional
   requirement that only became visible once it was rendered in the real UI.

The prompt now also states the service target inline
(`service target 12 minutes`) so the model explains *why* a ticket is at risk
rather than just repeating the marker.

**Adopted:** yes — this is what ships.

## How failure is handled

`parse_llm_reply()` splits the reply on the four labels. If the model answers
in the wrong shape, or Ollama is unreachable, `analyse()` returns
`mode: "heuristic"` with the same output structure from `heuristic_analysis()`,
and the UI shows a badge saying which path ran. The prompt is never a single
point of failure for the POS.

Covered by `tests/test_ai_mode.py`:
`test_analysis_uses_the_model_when_it_answers_in_format` and
`test_analysis_falls_back_when_ollama_is_unreachable`.

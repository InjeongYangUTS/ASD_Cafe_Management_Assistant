# Technical Report - Student 1 sections

Hangyeol Yi (14647705), Customer Feedback & Reviews
Assessment 1 – Release 0, 41026 Advanced Software Development

Paste each section into the shared report document under the matching heading.

---

## 2.2 Student 1 – Customer Feedback & Reviews

This feature is the cafe's ear. A customer leaves a star rating and a comment
after a visit; staff read every review on one board, reply to the ones that
need answering, and ask AI-Mode which menu items are drawing complaints and
which are drawing praise, so the answer points at something the cafe can
actually change.

### 2.2.1 Functional requirements

| ID | Functional Requirement |
|---|---|
| FR1 | A customer can submit a review consisting of a star rating from 1 to 5, a short title and a comment. Nothing else is asked of them. |
| FR2 | The system classifies each review on arrival - sentiment, a category and the issues or praise it mentions - so no review is ever unlabelled on the staff board. |
| FR3 | A customer can see the reviews they have written, and only those. Another customer's reviews are never returned to them. |
| FR4 | A customer can edit their own review. The change is recorded and the review is re-classified. |
| FR5 | A customer can delete their own review, after confirming it in the page. |
| FR6 | A customer can see the cafe's reply on their own review. |
| FR7 | Staff can view every review in the feedback database on one board, with the headline figures - total reviews, average rating, how many are waiting for a reply, how many are negative. |
| FR8 | Staff can search the reviews by free text across the title, the comment and the customer's name. |
| FR9 | Staff can restrict the board to a date range, sort by newest, oldest, highest rating or lowest rating, and clear every filter with one control. |
| FR10 | Staff can write a reply to a review. The reply is stored against the review and becomes visible to the customer who wrote it. |
| FR11 | Staff can ask AI-Mode a question in their own words and receive an answer drawn only from the reviews in the database. |
| FR12 | The AI answer names which menu items customers complain about and which they praise, with the evidence behind each, and recommends what to act on first. |
| FR13 | A question about one menu item is answered about that item alone, not with a summary of the whole store. |
| FR14 | Staff can re-run the language model over reviews that currently hold a rule-based verdict, upgrading the classification without re-entering any data. |
| FR15 | Every create, update, delete, reply and analysis appends an audit record, and the audit record survives the deletion of the review it describes. |
| FR16 | The Feedback API exposes store-wide figures and per-review data over HTTP, so other features can read feedback without opening this feature's database. |

### 2.2.2 Non-functional requirements

| ID | Category | Requirement | How it is verified |
|---|---|---|---|
| NFR1 | Performance | Reads used while serving - the review list, the customer's own reviews, the staff board - return within 500 ms for 19 of 20 requests. | The agentic loop measures 20 samples of `GET /api/feedback` on every run and fails the build otherwise. Latest run: 20/20, slowest 33 ms. |
| NFR2 | Security - privacy | A customer can read, edit and delete their own reviews and no one else's. Identity is taken from the signed session cookie, never from the request body. | Forgery probes: `PUT` with another customer's `customer_id` in the body, and with `actor_role: STAFF`, both answered 401/403 rather than 200. Regression tests in `tests/test_database_api.py`. |
| NFR3 | Security - authorisation | Writing a staff reply requires a staff session. | `respond()` reads `session["staff_id"]`; a request without one is refused. |
| NFR4 | Data integrity | An audit record outlives the review it describes, so a deletion can still be proven after the fact. | `store_logs.feedback_id` is deliberately not a foreign key. The agentic loop asserts that surviving `DELETED` entries exist whose review is gone. Latest run: 5. |
| NFR5 | Reliability | The AI answer never contradicts the measured data. | The measured per-menu figures are computed in Python first; the model's reply is checked against them and the measured answer replaces any section that disagrees. |
| NFR6 | Fault tolerance | The feature stays usable when Ollama, the Order service or the Menu service is unreachable. | Peer failures are remembered for 60 seconds by a small circuit guard so a dead peer costs one timeout, not one per request; AI-Mode falls back to a deterministic rule-based answer and says which path ran. |
| NFR7 | Architecture | No service opens a database file it does not own. | `feedback.db` is opened only by `student-1-database`; the backend and frontend reach it through `/db/*` over HTTP. |
| NFR8 | Usability | The two screens reuse the shared team theme, and every operation is performable from the browser without an API client. | All feature styling is namespaced `s1-` on top of `shared/css/style.css`, so a teammate's change to the shared sheet cannot break these pages. |
| NFR9 | Correctness of display | Times are shown in the cafe's own timezone, not the server's. | Timestamps are stored in UTC and rendered through a Jinja filter in `Australia/Sydney`; covered by unit tests. |
| NFR10 | Maintainability | Frontend, backend and database are separately deployable, and every outbound call lives in one module. | Three Dockerfiles; all HTTP clients in `backend/services/database_api.py`, the model client in `backend/services/llm_client.py`. |
| NFR11 | Testability | The feature has automated tests that run with no container started. | 47 tests - 21 database/API, 26 AI-Mode - run in the `lint-and-unit` job before any image is built. |
| NFR12 | Portability | The feature runs from a clean checkout with Docker alone; the database seeds itself on first boot. | `docker compose up --build`; 30 reviews and 82 audit records are created automatically. |

### 2.2.3 Individual feature plan

The feature was built in four increments. Each one ends with something that
can be demonstrated in a browser, not merely something that compiles.

| Increment | Scope | Done when |
|---|---|---|
| 1. Data foundation | `customer_feedback` and `store_logs`; the seed script; the database service and its `/db` CRUD API. | 30 reviews and 82 audit records seed on first boot and are readable over HTTP, and both tables exceed the Release 0 ten-record minimum. |
| 2. Feedback logic | Backend/API: review CRUD, ownership enforcement, the staff reply, the audit trail written inside the same transaction as the write it describes, and the store-wide summary. | A create → read → update → delete round trip passes, and a write attributed to another customer is refused. |
| 3. Screens | Customer screen (submit at the top, own reviews below) and staff board (question box at the top, all reviews below) with search, date range and sort. | Both screens work end to end in the browser with no API client, and a staff reply appears on the customer's own review. |
| 4. AI-Mode and the agentic loop | The measurement layer, the prompt assets, the Ollama call, the validation of the reply against the measured facts, and the PLAN → ACT → OBSERVE → ADAPT loop. | AI-Mode names the complained-about and praised menu items correctly, the fallback is proven by stopping Ollama, and the loop reports PASS with its log written to `agentic/logs/`. |

Two ordering decisions shaped the work. The data layer came first because
every later part depends on the shape of a review. AI-Mode came last because
it needed a realistic body of reviews to reason about - a per-menu breakdown
is meaningless until enough reviews mention enough menu items, which is why
the seed spreads 30 reviews across roughly 45 days rather than creating them
all at once.

### 2.2.4 Risk management plan

L = likelihood, I = impact.

| ID | Risk | L | I | Mitigation | Status |
|---|---|---|---|---|---|
| R1 | One customer can reach another customer's reviews. | Medium | High | Identity is read from the signed session cookie only. The `customer_id` in a request body is ignored, and a staff role claimed in a request body is ignored. Cross-customer probes are unit tests, so a regression fails CI. | Mitigated - verified by attempting the attack; all forgery probes return 401. |
| R2 | Seeded demo customers collide with real sign-ups, so a new account inherits someone else's reviews. | Medium | High | Seeded customers are numbered from 101 upward, well clear of the ids the shared auth service issues. | Mitigated after the defect was observed - a real registration had picked up a seeded customer's reviews and could edit them. |
| R3 | Ollama is slow or unreachable during the demonstration. | Medium | High | Every AI answer has a deterministic rule-based equivalent with the same shape, and the panel states which path produced it. The model is pulled once into a named volume. | Mitigated - demonstrated working in both modes. |
| R4 | The language model states something the reviews do not support - inventing a menu item, or crowning a single-review item as the worst. | High | High | The per-menu figures are computed in Python before the model is called; the prompt receives that summary rather than raw rows; the reply is then checked against the figures and any contradicted section is replaced. | Mitigated - see 13.3. |
| R5 | A teammate's change to a shared file breaks my screens. | Medium | Medium | All feature code lives under `student-1/`. Shared files are touched in three places only: one compose block, one dashboard card each. Every style rule my pages depend on is namespaced `s1-`, so the shared stylesheet can change underneath them. | Mitigated - confirmed by rendering my screens against a teammate's rewritten stylesheet. |
| R6 | Deleting a review destroys the evidence that it existed. | Medium | Medium | `store_logs.feedback_id` is a plain integer with no cascade, so the audit record outlives the review. The agentic loop asserts on every run that orphaned `DELETED` entries are present. | Controlled - enforced on every CI run. |
| R7 | A peer service being down makes my pages slow rather than merely incomplete. | Medium | Medium | Peer calls have a shorter timeout than my own database calls, and a failure is remembered for 60 seconds so it is not re-paid on every request. | Mitigated after the defect was observed - `GET /api/summary` had exceeded ten seconds; it now answers in tens of milliseconds. |
| R8 | Individual work is not integrated in time and scores zero. | Low | High | Integrated first, refined second: the three services ran under the shared `docker-compose.yml` before extra functionality was added. | Mitigated - running under the shared compose file. |

### 2.2.5 Data design

#### Conceptual design

A **customer** writes a **review** about a **visit** to the cafe. A review
carries a rating and a comment, and nothing more is required of the person
writing it. **Staff** read reviews and may attach a **reply** to one.
**AI-Mode** reads reviews and produces a **classification** - a sentiment, a
category and the issues or praise the review mentions. Everything that
happens to a review is recorded as an **audit entry**.

Two concepts are mine: the **Review** and the **Audit Entry**. The customer
and the staff member are referenced but owned by the shared authentication
service; the menu items a review talks about are owned by the Menu feature.
The reply and the classification are not separate entities - a review has at
most one of each, so they are attributes of the review rather than tables of
their own.

#### ERD

```
┌──────────────────────────────┐              ┌─────────────────────────────┐
│      customer_feedback       │              │         store_logs          │
├──────────────────────────────┤              ├─────────────────────────────┤
│ PK  id                       │              │ PK  id                      │
│     customer_id      ─ ─ ─ ─ ┼ ─ ▶ shared   │     feedback_id  · · · · ·  │
│     customer_name   (snapshot)     auth     │     entity                  │
│     order_id         ─ ─ ─ ─ ┼ ─ ▶ Order    │     action                  │
│     order_number    (snapshot)     service  │     actor                   │
│     rating          1–5      │              │     actor_role              │
│     title                    │   1      0..n│     detail                  │
│     comment                  │──· · · · · ──│     created_at              │
│     category                 │              └─────────────────────────────┘
│     status                   │
│     staff_response           │   ─ ─ ─  reference across a service boundary
│     sentiment                │          (no foreign key - different database)
│     sentiment_score          │
│     ai_summary               │   · · ·  deliberate soft reference
│     ai_issues       (JSON)   │          (no foreign key - the log must
│     ai_model                 │           outlive the row it describes)
│     analysed_at              │
│     submitted_at             │
│     updated_at               │
└──────────────────────────────┘
```

#### Logical design

The model is in third normal form inside the boundary I own, with three
deliberate departures, each made for a reason rather than for convenience.

**`customer_name` is stored on the review.** It duplicates a value owned by
the shared authentication service. It is a snapshot taken when the review was
written, not a cache: a review must still render with the author's name when
the authentication service is down, and a foreign key cannot cross a service
boundary because the referenced table lives in a database this service is not
allowed to open. `customer_id` is likewise a plain integer for the same
reason, and `order_id` / `order_number` are the same pattern pointing at the
Order service.

**The AI classification lives on the review rather than in its own table.** A
review has exactly one current verdict, and re-analysing overwrites it. A
separate table would model a history nobody reads, and would turn every
render of the staff board into a join. The columns are nullable because a
review is valid before it has been analysed; in practice every review is
classified the moment it arrives, so the board is never showing blanks.

**`ai_issues` holds a JSON array.** This is denormalised on purpose. The tags
are a closed vocabulary read as a set and never queried individually, and a
child table would add a join to every review read to store, typically, two
short strings.

**`store_logs.feedback_id` is not a foreign key.** This is the one departure
worth arguing for explicitly. Every other child table in this project
cascades on delete; this one must not. The purpose of the table is to record
what happened to a review, including its deletion, so a cascade would erase
precisely the evidence the table exists to keep. The consequence is accepted
and visible: the table contains orphaned rows by design, and the agentic loop
asserts on every run that they are there.

#### Physical design

SQLite, one file - `feedback.db` - opened by the `student-1-database`
container and by nothing else, persisted in a named Docker volume so data
survives a restart. Foreign keys are enabled explicitly, since SQLite does
not enforce them by default.

Validity is enforced in the schema rather than only in application code, so
an invalid row cannot be written even by a direct call to the database API:
`rating` is constrained to 1–5, `sentiment_score` to −1.0…1.0, and `category`,
`status`, `sentiment`, `action` and `actor_role` are each restricted to their
permitted values. A trigger keeps `updated_at` current on every update, with
a guard (`WHEN NEW.updated_at = OLD.updated_at`) that stops it recursing into
itself.

Four indexes on `customer_feedback` and three on `store_logs` support the
queries the application actually runs - a customer's own reviews
(`customer_id`), the staff board's default order (`submitted_at`), the
headline counts (`status`, `sentiment`), and the audit trail of one review
(`feedback_id`).

| Table | Rows seeded | Purpose | Key constraints |
|---|---|---|---|
| `customer_feedback` | 30 | One row per review, with the staff reply and the AI classification held alongside it. | `CHECK` on `rating`, `category`, `status`, `sentiment`, `sentiment_score`; `comment` NOT NULL; trigger maintains `updated_at`. |
| `store_logs` | 82 | Append-only audit trail of every create, update, delete, reply and analysis. | `CHECK` on `action` and `actor_role`; `feedback_id` intentionally carries no foreign key so the entry survives the deletion it records. |

The seed spreads the 30 reviews over roughly 45 days and includes audit
entries for reviews that no longer exist, so the no-cascade decision is
demonstrable in the seeded state rather than only after someone deletes
something during the demonstration.

---

## 9.1 student-1.yml

Builds and validates the three microservices of the Customer Feedback &
Reviews feature. It is triggered by any push or pull request touching
`student-1/`, `docker-compose.yml` or the workflow file itself, and can also
be run manually.

| Job | Steps | What it proves |
|---|---|---|
| `lint-and-unit` | Check out; Python 3.11; install the backend and frontend requirements; `compileall` every module; assert all eight prompt files exist and still contain their `{{PLACEHOLDER}}` tokens; run the seed script; run pytest. | The code compiles, the prompt assets have not been emptied or had a placeholder renamed out from under the loader, the seed produces the required data, and 47 tests pass - none of which needs a container, so a mistake is reported in about a minute. |
| `build-images` | `docker compose config --quiet` to validate the shared compose file, then build the database, backend and frontend images. | All three containers build from a clean checkout, and my compose block is still syntactically valid after a teammate has edited the same file. |
| `smoke-check` | Start the three services; poll `/db/health`, `/api/health`, `/health`, `/review` and `/reviews` until they answer 200; read `/db/stats` and fail if either table holds fewer than ten rows; run the CRUD smoke test; dump container logs on failure; tear down. | The services actually run together, the seeded data meets the Release 0 minimum, both screens render, and create → read → update → delete works against the live stack. |
| `agentic-loop` | Start the services, wait for the backend, run `agentic_loop.py --no-ai --no-input`, upload `agentic/logs/` as an artefact. | The database, endpoint and NFR checks still pass against a running stack. The loop's exit code fails the job, so it is a gate rather than a report. |
| `evidence-pack` | Generate `report.json`, `report.md` and `run-view.md` carrying the run id, commit SHA and branch; upload them. | Each run leaves a machine-readable record that can be cited in this report. |

Three details are deliberate.

The stack is started from the team's shared `docker-compose.yml` rather than a
CI-only file, so a green build is evidence about the real deployment - but
only my three services are started, because starting the whole team stack
would make my workflow fail whenever a teammate's container is broken, which
tells me nothing about my own code.

The prompt-placeholder check exists because the prompt loader raises if a
`{{PLACEHOLDER}}` is left unfilled at render time. That failure would
otherwise appear at runtime, in front of a user, rather than in CI.

The agentic loop runs with `--no-ai`. A GitHub runner has no GPU, and pulling
a model would take longer than the job allows, so the LLM steps are skipped
and the deterministic checks still gate the build. AI-Mode is demonstrated
locally and in the showcase video. Claiming the model ran in CI when it did
not would be false evidence, so the workflow says so in a comment at the top
of the file and in the generated report.

---

## 13.2 Individual prompt assets (Student 1)

Eight prompt assets are versioned under `student-1/prompts/`, four used by
AI-Mode in production and four by the agentic loop. Each is a plain text file
with `{{PLACEHOLDER}}` tokens filled at render time by
`services/prompt_loader.py`, which raises if any placeholder is left unfilled
- a prompt cannot silently reach the model half-built.

| # | Asset | Used for | Runs where |
|---|---|---|---|
| 01 | `service/ask_system_prompt.txt` | The persona and the rules AI-Mode must not break | Production - every staff question |
| 02 | `service/ask_task_prompt.txt` | The staff question plus the measured review summary (`{{REVIEW_SUMMARY}}`, `{{STAFF_QUESTION}}`) | Production - every staff question |
| 03 | `service/sentiment_system_prompt.txt` | Classifying one review | Production - the re-check pass |
| 04 | `service/sentiment_task_prompt.txt` | The review text to classify | Production - the re-check pass |
| 05–08 | `agentic/implementation_*`, `agentic/review_*` | The implementation agent's recommendation and the review agent's critique of it (`{{VALIDATION_EVIDENCE}}`, `{{IMPLEMENTATION_RECOMMENDATION}}`) | Production - `agentic_loop.py` |

**Context management.** Four rules were applied throughout. *Measure first,
then ask.* The prompt receives a computed summary - per-menu counts, average
ratings, the issue tags that actually occurred - never database rows, so a
300-review store and a 30-review store produce prompts of almost the same
size. *Strip what the model does not need.* No customer names, no primary
keys, no SQL. *Compute the facts, ask only for the judgement.* Counts,
averages and rankings are calculated in Python and given to the model to
quote, which is also what makes the rule-based fallback possible: the same
figures answer the question when Ollama is unavailable. *Constrain the output
and then validate it.* The system prompt forbids bullet-point dumps and
invented menu items, and the reply is checked structurally before it is
shown.

**Prompt engineering, v1 to v3 (assets 01 and 02).** Version 1 sent the raw
review rows and asked "what do customers think?". The model wrote four
hundred words, recalculated averages from the rows and got them wrong, and
named a menu item the cafe does not sell. Version 2 replaced the rows with
the measured summary and added a system prompt stating that the answer must
come only from the supplied figures - the numbers became correct, because the
model was quoting rather than deriving them. Version 3 added two rules that
only became necessary once the feature was used the way staff actually use
it: *answer about the item that was asked about, and nothing else*, because a
question about the Flat White was being answered with a tour of the whole
menu; and *do not present a single review as a pattern*, because the model
had crowned an item with one bad review as the worst on the menu. The second
rule is also enforced in code - a superlative claim about an item with too
little evidence is overridden by the measured ranking before the answer is
displayed.

---

## 13.3 Agentic loop record (Student 1)

`student-1/agentic_loop.py` implements PLAN → ACT → OBSERVE → ADAPT with two
different models and a human decision point: an **implementation agent**
(`llama3.2`) proposes improvements from the validation evidence, and a
separate **review agent** (`qwen2.5:0.5b`) critiques that proposal. Using two
models is deliberate - a recommendation is not reviewed by the model that
wrote it. Every run is written to `agentic/logs/` twice, as Markdown for
reading and JSONL for processing, and both are kept in the repository.

The record below is the run that produced the most consequential change.

| Stage | Record |
|---|---|
| **PLAN** | Validate the three microservices: both tables hold ten or more records, every endpoint answers, `GET /api/feedback` returns within 500 ms for 19 of 20 requests, and AI-Mode answers a staff question through Ollama. The audit trail must contain a `DELETED` entry whose review no longer exists, proving `store_logs` has no delete cascade. |
| **ACT** | The checks were executed against the running stack: database validation, six endpoints, the NFR benchmark, and a live AI-Mode question. |
| **OBSERVE** | `NFR FAIL - 0/20 requests within 500 ms (slowest 2099 ms)`. Everything else passed. |
| **Problem identified** | The failure was not in any endpoint. `.env` was being loaded *after* `services/database_api.py` had already read `DB_SERVICE_URL` at import time, so the URL fell back to `localhost`, which resolves to IPv6 first on Windows and cost roughly two seconds per call before falling back to IPv4. Every read in the feature was paying it; the NFR benchmark was simply the first thing that measured it. |
| **ADAPT** | The weakest area was performance, so the next iteration focused there. |
| **Changes made** | 1. `backend/services/__init__.py` now loads `.env` at package import, before any submodule reads an environment variable. 2. The default was changed from `localhost` to an explicit host. 3. The NFR check remained in the loop as the regression test. |
| **Final result** | Re-run converged in one iteration: **NFR PASS - 20/20 requests within 500 ms, slowest 33 ms.** Latest run `agentic/logs/loop-20260903-055853.md` reports PASS on all four areas: 30 reviews, 100 audit records, 5 surviving `DELETED` entries, six endpoints answering, and AI-Mode answering through `llama3.2`. |

**A second finding, only visible against a real model.** With Ollama running,
a question about which items draw complaints was answered with a
bullet-point dump of every menu item and its count - accurate, but not an
answer, and unreadable on the staff board. Tightening the prompt reduced it
but did not eliminate it, because the model's compliance varies between runs.
The fix keeps the division of labour explicit: the model writes the prose,
but it does not get to replace the analysis. `answer_question()` now detects
a structural list in the reply and substitutes the deterministic answer built
from the measured figures. A related check overrides any superlative claim
about a menu item whose evidence is a single review. Neither defect could
have been found against a stub - both required a real model and real seeded
data.

---

## 14 Known issues (Student 1 rows)

| Issue | Effect | Cause |
|---|---|---|
| `customer_name` is a snapshot and is never refreshed. | If a customer changes their display name, reviews they wrote earlier keep the old name. | The name is stored at submission time so a review renders when the authentication service is down. Refreshing it would require either a foreign key across a service boundary or a background reconciliation, neither of which was in scope for Release 0. |
| `order_id` and `order_number` are stored but unused. | A review cannot yet be tied to the visit it describes, so the per-menu analysis relies on what the customer wrote rather than on what they bought. | Nothing verifies the link yet, and an order number displayed beside a review reads as verified whether or not it is. The columns exist for Release 1. |
| The review agent is a very small model. | `qwen2.5:0.5b` sometimes returns a vague critique and occasionally garbles a number it was given. | It is one of the two approved models and was chosen for the review role because it is fast enough to run on every loop iteration. Its output is advisory: the loop's pass/fail decision comes from the deterministic checks, never from the model. |
| AI-Mode is not exercised in CI. | A change that breaks the Ollama call would not be caught by the pipeline. | A GitHub runner has no GPU and no model. The loop runs `--no-ai` there and the LLM path is demonstrated locally and in the video. |
| Only my three services and the shared entry point are started by my workflow. | My pipeline does not prove the fully integrated application. | Starting the whole team stack would fail my workflow whenever a teammate's container is broken, which says nothing about my own code. Integration is demonstrated by running the shared compose file locally. |

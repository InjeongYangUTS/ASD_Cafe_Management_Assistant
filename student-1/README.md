# Student 1 - Customer Feedback & Reviews

**Hangyeol Yi (14647705)** · Group 48 · Cafe Management Assistant · Release 0

Customers leave a star rating and a comment. Staff read every review on one
board and can ask a local LLM questions about them, such as which menu items
draw the most complaints.

---

## Microservices

| Service | Container | Port | Responsibility |
|---|---|---|---|
| Frontend | `student-1-frontend` | 5110 | Two HTMX screens: `/review` (customer), `/reviews` (staff) |
| Backend / API | `student-1-backend` | 8100 | Review logic, ownership rules, AI-Mode |
| Database | `student-1-database` | 7100 | Owns `feedback.db`, exposes it over `/db/*` |

```
Browser
   |  HTMX
   v
student-1-frontend  :5110
   |  HTTP
   v
student-1-backend   :8100 ----> Ollama :11434/v1 ----> llama3.2
   |  HTTP                 (AI-Mode)
   v
student-1-database  :7100
   |
   v
feedback.db (SQLite)
```

Cross-feature reads (order history, menu names) go to the Order service's
HTTP API. No service here opens another student's SQLite file, and no other
service opens `feedback.db`.

---

## Database

`feedback.db` is owned exclusively by `student-1-database`.

### `customer_feedback`
Customer id and name, order id and number (reference + snapshot), rating,
title, comment, derived category, staff workflow status, staff response,
and the AI columns (`sentiment`, `sentiment_score`, `ai_summary`,
`ai_issues`, `ai_model`, `analysed_at`).

### `store_logs`
Append-only audit trail: `CREATED`, `UPDATED`, `DELETED`, `ANALYSED`,
`STATUS_CHANGED`, `RESPONDED`, with the actor and their role.

`store_logs` has no foreign key cascade on `feedback_id`. The table records
deletions, so a log entry has to outlive the row it describes. This leaves
orphaned rows in the table by design.
`test_audit_trail_survives_the_delete` guards it.

Seed data: 30 reviews, 82 audit records, both over the Release 0 minimum of
ten. Every review arrives with a rule-based verdict; 15 of the seeded reviews
still carry that verdict, so the staff board's re-check button has live work
to do with the model.

---

## Design decisions

**The customer never picks a category.** They give a star rating and a
comment. The backend derives `category` from the wording
(`ai.classify_category`). Staff can still filter by category.

**AI values have exactly one entry point.** `PUT /db/feedback/<id>` ignores
`sentiment` and `sentiment_score`; they can only be written through
`PUT /db/feedback/<id>/analysis`, which logs an `ANALYSED` event by the
`ai` actor. A customer editing their own review cannot set the sentiment the
staff board reads.

---

## AI-Mode

Configured the way the course guide sets out: the OpenAI SDK pointed at
Ollama's OpenAI-compatible endpoint.

```
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2              # approved LLM from the registration form
OLLAMA_REVIEW_MODEL=qwen2.5:0.5b   # agentic loop review agent only
```

Request path: `frontend -> backend -> Ollama -> LLM -> backend -> frontend`.
The backend builds the prompt, so the model name and the context stay out
of the browser.

Three layers run in order:

1. **Measure.** Deterministic Python computes rating distribution, issue-tag
   frequencies, per-menu-item breakdowns and priority scores. These numbers
   are the prompt context: a compact summary rather than hundreds of raw rows.
2. **Ask.** The LLM writes the prose on top of those facts.
3. **Validate.** The answer is checked back against the measured facts. Any
   override is reported on screen.

Concretely, the answer is overridden when the model returns POSITIVE for a
one-star review, when it names a menu item with no review evidence, or when
it wanders onto other items after being asked about one. A question about an
item nobody has reviewed is answered without calling the model at all.

If Ollama is unreachable every path falls back to a rule-based answer with
the same shape, and the screen reports which path ran.

---

## Prompts

`prompts/` holds every prompt as a `.txt` file with `{{PLACEHOLDER}}`
substitution, so the wording can be reviewed without reading the source.

```
prompts/service/    ask_system_prompt.txt        staff question, system
                    ask_task_prompt.txt          {{REVIEW_SUMMARY}} {{STAFF_QUESTION}}
                    sentiment_system_prompt.txt  one-review classifier, system
                    sentiment_task_prompt.txt    {{RATING}} {{COMMENT}} ...
prompts/agentic/    implementation_*.txt         {{VALIDATION_EVIDENCE}}
                    review_*.txt                 {{IMPLEMENTATION_RECOMMENDATION}}
```

An unfilled placeholder raises, because a stray `{{...}}` reaching the model
reads as an instruction.

---

## Agentic loop

```bash
python student-1/agentic_loop.py              # interactive
python student-1/agentic_loop.py --no-input   # CI
python student-1/agentic_loop.py --no-ai      # deterministic checks only
```

`PLAN → ACT → OBSERVE → ADAPT`, with the Lab 03 multi-model workflow:

| Stage | What runs |
|---|---|
| OBSERVE | Data quality, live endpoints, NFR (19/20 reads under 500 ms), AI-Mode |
| Implementation agent | `llama3.2` proposes two evidence-backed improvements |
| Review agent | `qwen2.5:0.5b` reviews that proposal, so a second model checks the first |
| Human review | Accept / Partially Accept / Reject. The human decides |
| ADAPT | The action that follows. A failed check outranks any agent advice |

Every run writes `agentic/logs/loop-<timestamp>.md` and `.jsonl`.

**The loop found two real defects**, both fixed:

| Finding | Cause | Fix |
|---|---|---|
| NFR failed, 0/20 within 500 ms (slowest 2099 ms) | `.env` loaded *after* `database_api.py` read its URLs, so `DB_SERVICE_URL` fell back to `localhost`, which resolves IPv6 first on Windows at ~2 s per call | Load `.env` in `services/__init__.py`, before any submodule import |
| `GET /api/summary` timed out past 10 s | Every request re-probed the Order and Menu services, which were down | Short peer timeout, a 60-second failure memory, and a menu vocabulary cache |

After: `GET /api/feedback` 2099 ms → **28 ms**; NFR **20/20**, slowest 39 ms.

---

## Running it

### With Docker Compose (the supported way)

From the repository root:

```bash
docker compose up --build student-1-database student-1-backend student-1-frontend
```

Then open `http://localhost:5100` for the shared entry point, sign in, and
use the **Feedback & Reviews** card.

Demonstration accounts: `customer@test.com` / `customer123`,
`staff@test.com` / `staff123`.

### Locally, without Docker

```bash
cp student-1/.env.example student-1/.env
pip install -r student-1/backend/requirements.txt
./run_local_s1.sh
```

`.env` uses `127.0.0.1` instead of `localhost`. On Windows, resolving
`localhost` tries IPv6 first and costs roughly two seconds per call.

### Tests

```bash
cd student-1 && python -m pytest tests -v      # 47 tests, no containers needed
python student-1/tests/smoke_database.py       # CRUD against a running service
```

---

## Sign-in

This service has no login of its own. The shared entry point on port 5100
signs the user in and stores the identity in a Flask session cookie;
cookies are scoped by host rather than by port, so this service reads the
same cookie by using the same `SECRET_KEY`.

Identity is never taken from a URL or a form field, so a customer cannot
reach another customer's review by changing a number in the address bar.
`require_owner()` in the backend enforces the same rule server-side and
returns 403.

---

## API

### Database service (7100)

```
GET    /db/health
GET    /db/stats
GET    /db/feedback              ?customer_id= &status= &sentiment= &category=
                                 &min_rating= &max_rating= &analysed= &limit=
POST   /db/feedback
GET    /db/feedback/<id>
PUT    /db/feedback/<id>
DELETE /db/feedback/<id>
PUT    /db/feedback/<id>/analysis
GET    /db/feedback/<id>/logs
GET    /db/logs                  ?feedback_id= &action= &limit=
POST   /db/logs
DELETE /db/logs/<id>
```

### Backend / API (8100)

```
GET    /api/health               ?deep=1 for the full dependency report
GET    /api/feedback
POST   /api/feedback
GET    /api/feedback/<id>
PUT    /api/feedback/<id>
DELETE /api/feedback/<id>
PUT    /api/feedback/<id>/status
POST   /api/feedback/<id>/response
GET    /api/feedback/<id>/logs
GET    /api/logs
GET    /api/summary              review figures for the rest of the team
GET    /api/orders               reviewable orders for a customer
POST   /api/ai/ask               AI-Mode answer to a staff question
POST   /api/ai/analyse/<id>
POST   /api/ai/analyse-pending
```

`GET /api/summary` is the endpoint other students should call for review
data. Please do not read `feedback.db`.

### Frontend (5110)

```
GET  /review     customer: leave a review, edit or delete your own
GET  /reviews    staff: every review, ask the AI a question
GET  /health
```

---

## Known issues and limitations

- **The local models are small.** They sometimes mislabel the numbers they
  are given, such as calling a 2.00 average "high". The measured tables and
  the validation layer stay correct; the wording is what slips. A larger
  model fixes it, at the cost of a much slower cold start.
- **AI-Mode is slow on a machine without a GPU.** A staff question takes 45
  to 75 seconds on the development laptop. The page shows a waiting panel
  for the duration.
- **`llama3.1:8b` was tried as the review agent and dropped.** Its cold
  start ran to minutes on the development machine and timed the agent out,
  so `OLLAMA_REVIEW_MODEL` defaults to `qwen2.5:0.5b`.
- **Menu attribution works on the whole review, not on each sentence.** A
  review that praises the flat white and complains about the grinder noise
  attaches both tags to Flat White. Sentence-level attribution is Release 1
  work.
- **AI-Mode is not exercised in CI.** A GitHub runner has no model, so the
  workflow runs the agentic loop with `--no-ai`. The LLM path is shown
  locally and in the video instead.
- **Team numbering is unresolved.** The approved registration form calls this
  feature Student 1; the original `docker-compose.yml` comments called it
  Student 1 and gave 8100 to Inventory. This feature follows the registration
  form. `student-4-backend`'s `INVENTORY_SERVICE_URL` has been pointed at a
  placeholder rather than at this service.
- **The Order service is optional.** Without it, reviews cannot be linked to
  an order and menu attribution falls back to `menu_terms.json`. Every
  response reports which source was used.

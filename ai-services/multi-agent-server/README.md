
# Cafe Management Assistant — Multi-Agent Server

## Overview

The Multi-Agent Server is a shared AI service for the Cafe Management Assistant project.

It uses three AI agents to process tasks, review generated answers, and allow a human to make the final decision.

The Multi-Agent Server runs as a shared Docker service on the cafe-net network. Student feature backends can communicate with it through HTTP requests.

The server can also run directly on the host machine for local development and testing.

## Architecture

The workflow follows this sequence:

1. **Planner Agent** — Analyses the task and available evidence, then creates a plan.
2. **Worker Agent** — Executes the plan and generates a response.
3. **Reviewer Agent** — Evaluates the Worker's response against the task and evidence.
4. **Human Review** — Allows a user to approve, correct, partially accept, or reject the response.

When a user requests a correction, the Worker revises its response and the Reviewer evaluates it again.

## Technologies

- Python
- Flask
- Flask-CORS
- Ollama
- Llama 3.1 8B
- JSON-based workflow audit logs

## Project Structure

```text
multi-agent-server/
├── app.py
├── config.py
├── planner.py
├── worker.py
├── reviewer.py
├── workflow.py
├── requirements.txt
├── test_app.py
├── test_workflow.py
├── README.md
└── logs/
```

## Setup

### 1. Install dependencies

From the `ai-services/multi-agent-server` directory:

```bash
python3 -m pip install -r requirements.txt
```

### 2. Start Ollama

Ensure Ollama is running locally and the required model is available.

```bash
ollama pull llama3.1:8b
```

The default Ollama address is:

```text
http://127.0.0.1:11434
```

### 3. Start the Multi-Agent Server

```bash
python3 app.py
```

The server listens on port `5800`.

For local testing, use:

```text
http://localhost:5800
```

## Docker Setup (Recommended for Group Members)

The Multi-Agent Server is included in the project's root `docker-compose.yml`.

### 1. Prerequisites

Install and start:

- Docker Desktop
- Ollama

Download the required AI model:

```bash
ollama pull llama3.1:8b
```

Ensure Ollama is running on port `11434`.

### 2. Start the Multi-Agent Server

Open a terminal in the project root directory and run:

```bash
docker compose build multi-agent-server
docker compose up -d --no-deps multi-agent-server
```

These commands build and start only the Multi-Agent Server without starting or rebuilding other student services.

### 3. Verify the Server

```bash
curl http://localhost:5800/health
```

Expected response:

```json
{
  "service": "multi-agent-server",
  "status": "ok"
}
```

### 4. Connect Student Features

Use the following server addresses:

| Where the request originates | Server URL |
|---|---|
| Student backend inside Docker on `cafe-net` | `http://multi-agent-server:5800` |
| Application running directly on the host | `http://localhost:5800` |

For example, a Python backend running inside Docker can use:

```python
import requests

MULTI_AGENT_URL = "http://multi-agent-server:5800"

response = requests.get(f"{MULTI_AGENT_URL}/health", timeout=10)
print(response.json())
```

Student backends should send workflow requests to the shared service rather than creating separate copies of the AI agents.

### 5. Workflow Logs

Workflow audit logs are stored in:

```text
ai-services/multi-agent-server/logs/
```

The directory is mounted into the Docker container at `/app/logs`, so workflow records survive container recreation.

Generated logs are excluded from Git.

### 6. Troubleshooting

Check the container status:

```bash
docker compose ps multi-agent-server
```

View server logs:

```bash
docker compose logs --tail=50 multi-agent-server
```

If port `5800` is already occupied, stop the other process using that port before starting the Docker service.

The Docker configuration connects to Ollama on the host through `host.docker.internal:11434`. Ensure Ollama is running and accessible from Docker.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Check server availability |
| POST | `/workflows` | Start a new multi-agent workflow |
| GET | `/workflows/<workflow_id>` | Retrieve a workflow and its history |
| POST | `/workflows/<workflow_id>/human-review` | Submit a human review decision |

### Create a Workflow

**POST** `/workflows`

Example request:

```json
{
  "task": "List the ingredients needed for a cappuccino.",
  "evidence": {
    "recipe": "Cappuccino",
    "ingredients": ["Espresso", "Milk"]
  }
}
```

The server runs the Planner, Worker and Reviewer sequentially.

A successful workflow contains a unique workflow ID, agent outputs, review information, status and audit history.

### Retrieve a Workflow

**GET** `/workflows/<workflow_id>`

Returns the stored workflow, including:

- Task and evidence
- Planner output
- Worker output
- Reviewer assessment
- Current workflow status
- Human review information
- Audit history

### Submit Human Review

**POST** `/workflows/<workflow_id>/human-review`

Supported decisions:

| Decision | Behaviour |
|---|---|
| `approve` | Accept the generated response and complete the workflow |
| `correct` | Send feedback to the Worker for revision and Reviewer re-evaluation |
| `partial_accept` | Record partial acceptance and complete the workflow |
| `reject` | Reject the response and complete the workflow |

Example approval request:

```json
{
  "decision": "approve",
  "comments": "The answer is correct."
}
```

Example correction request:

```json
{
  "decision": "correct",
  "comments": "Include the ingredient quantities."
}
```

Correction comments are required when the decision is `correct`.

After correction, the workflow returns to `awaiting_human_review`.

## Workflow Status

The workflow uses statuses including:

- `awaiting_human_review` — The agents have finished and a human decision is required.
- `completed` — A human review decision has finalised the workflow.
- `failed` — Workflow processing encountered an error.
- `revision_failed` — An error occurred during a requested correction.

## Audit Logging

Workflow information and history are saved as JSON files in the `logs/` directory.

Each workflow has a unique identifier.

Audit events include agent completion, human review decisions, corrections and revision outcomes.

Stored workflows can be retrieved after the server restarts.

The `logs/` directory is excluded from Git tracking.

## Automated Tests

Run all automated API and workflow tests:

```bash
python3 -m unittest test_app.py test_workflow.py
```

The automated suite contains 11 tests:

- 7 API tests
- 4 workflow tests

These tests use mocked agent responses and do not require a running Ollama instance.

A separate manual test has also been performed for recovering a workflow from its saved JSON file after clearing in-memory workflow data.

## Integration with Student Features

Student feature backends can communicate with the shared Multi-Agent Server through HTTP requests.

For example:

1. A student backend submits a task and relevant evidence to `POST /workflows`.
2. The server returns the workflow result.
3. The student frontend displays the Planner, Worker and Reviewer outputs.
4. The user submits a Human Review decision through the student backend.
5. The student backend forwards the decision to the Multi-Agent Server.
6. The updated workflow and audit history are displayed to the user.

When the student backend runs inside Docker, it must use a host-reachable address rather than `localhost` to contact the host-side Multi-Agent Server.

## Notes

- All three agents use `llama3.1:8b`.
- Ollama requests have a configured timeout of 120 seconds.
- The server uses evidence-based prompts to reduce unsupported responses, but AI-generated answers still require human verification.
- Workflow audit data is stored locally as JSON files.
- The service is intended for the project's development and demonstration environment; production authentication and deployment hardening are not included.

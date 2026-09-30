# Release 1 Integration Guide

This guide explains how to connect each student’s feature to the shared local MCP and RAG servers.

The settings below come from the existing repository code. Everyone should use the same settings so all five features work consistently.

**Integration owner:** Hangyeol Yi  
**Responsibilities:** Microservices integration and local MCP/RAG integration testing.

| Component | Owner | Code location |
|---|---|---|
| Shared MCP server | Injeong Yang | Branch: `shared-mcp-server`; folder: `ai-services/mcp-server/` |
| Shared RAG server | Ei Thandar | Branch: `shared-rag-server`; folder: `shared/rag/` |
| Docker Compose | Ong Ath Vongnathi | `docker-compose.yml` |
| Shared agentic loop | Stella Kwon | `student-4/agentic/` |
| Example client code | Stella Kwon | `student-4/backend/ai_services.py` |

## 1. How requests move through the system

The frontend sends requests to its own backend. The backend then contacts the shared MCP or RAG server. The RAG server uses Ollama to generate answers.

| Component | Where it runs |
|---|---|
| Feature frontend | In a Docker container (opened in the browser) |
| Feature backend/API | In a Docker container |
| Shared MCP server | On your computer, outside Docker |
| Shared RAG server | On your computer, outside Docker |
| Ollama | On your computer, outside Docker |
| Agentic loop | On your computer, outside Docker |

The frontend must only call its own backend. It must not call MCP or RAG directly.

MCP, RAG, Ollama, and the agentic loop are not started by Docker Compose.

## 2. Server addresses

Use `localhost` when connecting from your computer.

Use `host.docker.internal` when connecting from inside a Docker container.

| Service | Port | Address from your computer | Address from a container |
|---|---|---|---|
| RAG | 5600 | `http://localhost:5600` | `http://host.docker.internal:5600` |
| MCP | 5700 | `http://localhost:5700` | `http://host.docker.internal:5700` |
| Ollama | 11434 | `http://localhost:11434` | `http://host.docker.internal:11434` |

## 3. Backend settings

Set these environment variables for each backend:

| Variable | Inside Docker | Default outside Docker |
|---|---|---|
| `MCP_URL` | `http://host.docker.internal:5700` | `http://localhost:5700` |
| `RAG_URL` | `http://host.docker.internal:5600` | `http://localhost:5600` |
| `OLLAMA_URL` | `http://host.docker.internal:11434` | `http://localhost:11434` |
| `MCP_TIMEOUT` | `15` | `15` |
| `RAG_TIMEOUT` | `120` | `120` |

The timeouts are in seconds. They control how long the backend waits for a response.

Also add this setting to each backend service in `docker-compose.yml`:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

This lets the container reach services running on your computer.

## 4. Shared RAG server

The RAG server searches project documents. It can return relevant text or use that text to generate an answer through Ollama.

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Checks whether the RAG server is running |
| POST | `/retrieve` | Finds relevant text without calling the language model |
| POST | `/query` | Finds relevant text and asks Ollama to answer using it |

The `/health` response is:

```json
{
  "status": "ok",
  "service": "shared-rag"
}
```

Send questions to `/retrieve` or `/query` in this format:

```json
{
  "question": "How are reviews classified by sentiment?"
}
```

The `/query` response has this structure:

```json
{
  "question": "...",
  "answer": "...",
  "sources": [
    {
      "id": 1,
      "document": "student-1/review_policy.txt",
      "excerpt": "...",
      "coverage": 0.8
    }
  ],
  "confidence": "high",
  "status": "success"
}
```

- `answer`: the generated answer.
- `sources`: the documents and text used to support the answer.
- `confidence`: `high`, `medium`, `low`, or `insufficient`.
- `status`: `success` or `insufficient_context`.

Expected results:

| Situation | HTTP status | Response |
|---|---|---|
| An answer is available | 200 | `status: success`, with an answer, sources, and confidence |
| No relevant information is found | 200 | `status: insufficient_context`, `answer: null`, and `sources: []` |
| The question is empty | 400 | An error message |
| Ollama cannot be reached | 503 | An error message |

Store knowledge documents as `.txt` files in:

```text
shared/rag/knowledge/student-N/
```

Replace `N` with your student number in the project.

Separate paragraphs with a blank line. The server treats each paragraph as one searchable text section, called a **chunk**.

## 5. Shared MCP server

The MCP server uses FastMCP and must accept HTTP connections on port `5700`.

The example client in `student-4/backend/ai_services.py` supports both methods below. It detects which method the server provides.

| Connection method | Get the tool list | Run a tool |
|---|---|---|
| JSON-RPC (MCP Streamable HTTP) | `POST /mcp` with method `tools/list` | `POST /mcp` with method `tools/call` |
| REST | `GET /tools` | `POST /invoke` |

The server must also provide `GET /health` for the agentic loop and CI checks.

Rules for tools:

- Each tool belongs to one feature.
- Tools can only read data unless permission to change data is explicitly stated.
- If a requested tool is not registered, the server returns an error.
- The server checks that the tool’s inputs match its required format.
- Tools must access feature data through that feature’s backend/API. They must not access its database directly.

## 6. Routes required in every feature backend

Each feature backend must provide these three routes:

| Method | Path | What to send | What it returns |
|---|---|---|---|
| GET | `/api/ai/mcp` | No request body | `available`, `reason`, `count`, and `tools` |
| POST | `/api/ai/mcp` | `{"tool": "...", "arguments": {...}}` | The tool result in a structured format |
| POST | `/api/ai/rag` | `{"question": "..."}` | The result from RAG’s `/query` route |

Every response includes a `status` field. The HTTP status code follows the Lab 7 and Lab 8 pattern:

| `status` | HTTP | Meaning |
|---|---|---|
| `success` | 200 | Tool result or grounded answer returned |
| `insufficient_context` | 200 | RAG found no relevant evidence, so no answer was generated |
| `tool_error` | 200 | The tool ran and returned `isError: true` |
| `rejected` | 400 | Missing, unknown or out-of-range arguments (checked against the tool's `inputSchema` before the call) |
| `disabled` | 403 | Turned off with `MCP_ENABLED=false` or `RAG_ENABLED=false` (used in CI) |
| `not_registered` | 404 | The tool is not in the server's `tools/list` |
| `unavailable` | 503 | The shared server is not reachable |

The backend never invents a result when a server is down. The page keeps working and shows the reason.

Optional but recommended: record every MCP and RAG call in an audit log. Student 1 writes JSON lines with `request_id`, `timestamp`, `mode`, `name`, `input`, `status`, `duration_ms` and a result summary, and exposes them at `GET /api/ai/audit`.

## 7. What the frontend must show

| Panel or situation | Required content |
|---|---|
| MCP panel | Tool name, inputs, and a table showing the result |
| MCP unavailable | An error message explaining why it is unavailable |
| RAG panel | Answer, source document names, quoted source text, and confidence level |
| RAG has no relevant information | A clear message saying there is not enough information to answer |
| RAG low or insufficient confidence | A "needs staff review" flag (human review, Lecture 8) |

## 8. CI/CD with GitHub Actions

Keep the MCP and RAG integration code in the project.

However, CI does not start the shared servers, so both modes are disabled during CI runs.

The workflows must check that:

- The MCP and RAG backend routes exist.
- The panels handle missing servers properly and show an unavailable message without breaking the page.

Set `MCP_ENABLED: "false"` and `RAG_ENABLED: "false"` in the workflow `env`, then check that the routes answer `403` or `503`.

Use `.github/workflows/student-1.yml` or `.github/workflows/student-4.yml` as a reference.

## 9. How to start everything locally

1. Start Ollama.
2. Start the RAG server:

   ```bash
   python shared/rag/app.py
   ```

3. Start the MCP server using the instructions in `ai-services/mcp-server/`.
4. Build and start the Docker services:

   ```bash
   docker compose up --build
   ```

5. Open each feature’s frontend and test its MCP and RAG panels.

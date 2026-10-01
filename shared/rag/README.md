# Shared RAG Server

The shared Retrieval-Augmented Generation (RAG) server provides
knowledge-based question answering for the Cafe Management Assistant.

It runs locally using Flask and Ollama, outside Docker Compose.

## Requirements

- Python 3
- Ollama
- An installed Ollama model

## Installation

From the project root:

```bash
python3 -m pip install -r shared/rag/requirements.txt
```

## Configuration

The server uses the following environment variables:

| Variable | Default |
|---|---|
| RAG_HOST | 0.0.0.0 |
| RAG_PORT | 5600 |
| OLLAMA_URL | http://127.0.0.1:11434 |
| OLLAMA_MODEL | qwen2.5:0.5b |
| OLLAMA_TIMEOUT | 120 |

The configured Ollama model must be installed locally.

## Running the Server

Start Ollama, then run:

```bash
python3 shared/rag/app.py
```

The RAG server runs at:

http://127.0.0.1:5600

## Docker Connectivity

The shared RAG server runs locally, outside Docker Compose.

By default, it listens on `0.0.0.0:5600` to allow connections
from containerised feature backends.

Use the following addresses:

- From the host machine: `http://127.0.0.1:5600`
- From Docker Desktop containers: `http://host.docker.internal:5600`

The RAG server must be running before feature backends can
send requests to it.

Docker connectivity can be tested using:

```bash
docker run --rm curlimages/curl:latest \
  -i http://host.docker.internal:5600/health
```

A successful response returns HTTP 200 and the shared RAG
service status.

The server is intended for trusted local development and
should not be exposed to untrusted networks.

## Knowledge Directory

The server loads `.txt` documents from:

```text
shared/rag/knowledge/
```

Feature-specific documents can be placed in:

```text
knowledge/student-1/
knowledge/student-2/
knowledge/student-3/
knowledge/student-4/
knowledge/student-5/
```

Documents are loaded recursively when retrieval runs.

The current retriever uses keyword matching with a minimum
keyword coverage of 0.5. It does not yet use embeddings.

## API Endpoints

### GET /health

Checks whether the Flask server is running.

### POST /retrieve

Retrieves relevant knowledge without calling Ollama.

Example request:

```json
{
  "question": "What does the Menu and Recipe feature manage?"
}
```

### POST /query

Retrieves relevant knowledge and generates an answer using Ollama.

Example request:

```json
{
  "question": "What does the Menu and Recipe feature manage?"
}
```

A successful response includes:

- `question`: The submitted question.
- `answer`: The generated answer.
- `sources`: Retrieved document names, excerpts and coverage.
- `confidence`: Keyword-coverage category.
- `status`: Request outcome.

If the system cannot find sufficient context, it returns
`status: insufficient_context`.

Confidence is a retrieval heuristic, not a verified measure
of factual accuracy.

## Testing

From the project root:

```bash
python3 -m pytest shared/rag/tests/test_rag.py -v
```

## Integration

Each student is responsible for connecting their feature backend
and frontend to the shared RAG server.

The shared server must be running locally for requests to succeed.
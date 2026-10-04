# Cafe Management Assistant

The **Cafe Management Assistant** is a microservice-based application designed to support the daily operations of a small cafe.

The project was developed across two releases.

- **Release 0** established the core microservice application, feature-specific AI functions, Docker deployment, automated testing, and the Plan → Act → Observe → Adapt workflow.
- **Release 1** extended the system with one shared local MCP server, one shared local RAG server, grounded AI responses, and shared MCP/RAG validation modes.

Each student feature is separated into frontend, backend/API, and database responsibilities. Cross-feature communication is performed through HTTP APIs rather than direct database access.

---

## 1. Features

| Student | Feature | Main Capabilities |
|---|---|---|
| Student 1 – Hangyeol Yi | Customer Feedback & Reviews | Review CRUD, staff responses, sentiment/category analysis, AI-assisted feedback queries |
| Student 2 – Ei Thandar | Menu & Recipe Management | Menu CRUD, recipe CRUD, ingredient management, customer menu, AI-assisted pricing |
| Student 3 – Injeong Yang | Inventory & Restocking | Inventory CRUD, low-stock detection, supplier management, restock orders, AI recommendations |
| Student 4 – Stella Kwon | Order & Kitchen Management | POS, kitchen queue, order lifecycle, inventory integration, AI kitchen analysis |
| Student 5 – Ong Ath Vongnathi | Payment & Billing | Payment processing, transactions, refunds, validation, order integration |

The shared application also provides:

- Customer registration and login
- Staff registration and login
- Customer dashboard
- Staff dashboard
- Navigation to the five feature services

---

## 2. Architecture

The application uses a microservice architecture.

Each feature follows the same basic structure:

```text
Frontend
   ↓
Backend / API
   ↓
Database Service
```

Each feature owns its own data and business logic.

A feature does not directly read or modify another feature's database. Cross-feature communication uses backend APIs.

Release 1 adds shared local AI services:

```text
Feature Frontend
       ↓
Feature Backend / API
       ├──────────────→ Shared MCP Server
       │                       ↓
       │                 Registered Tools
       │                       ↓
       │                 Feature Adapters
       │
       └──────────────→ Shared RAG Server
                               ↓
                         Knowledge Retrieval
                               ↓
                             Ollama
```

Feature frontends do not directly communicate with the MCP server, RAG server, or another feature's database.

### Architecture Principles

- **Feature separation** – each student feature has its own frontend, backend/API, and database.
- **Database ownership** – each feature owns its own SQLite database.
- **API-based integration** – cross-feature data access is performed through HTTP APIs.
- **Backend-mediated AI access** – MCP and RAG requests are sent through the feature backend.
- **Local AI services** – MCP, RAG, Ollama, and the shared agentic loop run locally.
- **Graceful degradation** – core feature functionality remains available when shared AI services are unavailable.

---

## 3. Technology Stack

- **Python 3**
- **Flask**
- **SQLite**
- **HTML / CSS / JavaScript**
- **HTMX**
- **Requests**
- **Docker**
- **Docker Compose**
- **Ollama**
- **MCP SDK**
- **Pytest**
- **GitHub Actions**

---

## 4. Repository Structure

```text
ASD_Cafe_Management_Assistant/
│
├── .github/
│   └── workflows/
│       ├── student-1.yml
│       ├── student-2.yml
│       ├── student-3.yml
│       ├── student-4.yml
│       └── student-5.yml
│
├── ai-services/
│   └── mcp-server/
│       ├── server.py
│       ├── tools/
│       └── adapters/
│
├── shared/
│   ├── auth/
│   ├── database/
│   ├── frontend/
│   └── rag/
│       └── knowledge/
│
├── student-1/
│   ├── frontend/
│   ├── backend/
│   ├── database/
│   └── tests/
│
├── student-2/
│   ├── frontend/
│   ├── backend/
│   ├── database/
│   └── tests/
│
├── student-3/
│   ├── frontend/
│   ├── backend/
│   ├── database/
│   ├── assets/
│   └── tests/
│
├── student-4/
│   ├── frontend/
│   ├── backend/
│   ├── database/
│   ├── agentic/
│   └── tests/
│
├── student-5/
│   ├── frontend/
│   ├── backend/
│   ├── database/
│   └── tests/
│
├── docker-compose.yml
└── README.md
```

---

## 5. Service and Port Map

| Area | Frontend | Backend/API | Database |
|---|---:|---:|---:|
| Shared Application | 5100 | – | users.db |
| Student 1 – Feedback & Reviews | 5110 | 8100 | 7100 |
| Student 2 – Menu & Recipe | 5200 | 5201 | 5202 |
| Student 3 – Inventory & Restocking | 5300 | 8300 | 7300 |
| Student 4 – Order & Kitchen | 5400 | 8400 | 7400 |
| Student 5 – Payment & Billing | 5500 | 8500 | 7500 |
| Shared RAG Server | – | 5600 | – |
| Shared MCP Server | – | 5700 | – |
| Ollama | – | 11434 | – |

---

## 6. Running the Application

### Prerequisites

Install:

- Git
- Python 3
- Docker Desktop or Docker Engine with Docker Compose
- Ollama

Clone the repository:

```bash
git clone https://github.com/InjeongYangUTS/ASD_Cafe_Management_Assistant.git
cd ASD_Cafe_Management_Assistant
```

### Start Ollama

Ollama runs locally outside Docker Compose.

```bash
ollama serve
```

Ensure that the required local model is available before using AI-enabled functions.

### Start the Shared MCP Server

From the repository root:

```bash
python ai-services/mcp-server/server.py
```

The MCP server runs on:

```text
http://localhost:5700
```

Its Streamable HTTP endpoint is:

```text
http://localhost:5700/mcp
```

### Start the Shared RAG Server

Start the shared RAG implementation locally.

The configured RAG address is:

```text
http://localhost:5600
```

### Start the Containerised Application

From the repository root:

```bash
docker compose up --build -d
```

Check the running services:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs --tail=100
```

Stop the application:

```bash
docker compose down
```

The following services are intentionally not defined as Docker Compose services:

```text
Shared MCP Server
Shared RAG Server
Ollama
Shared Agentic Loop
```

---

## 7. Main Application URLs

Main shared application:

```text
http://localhost:5100
```

| Feature | URL |
|---|---|
| Shared Home | `http://localhost:5100/` |
| Customer Dashboard | `http://localhost:5100/customer-dashboard` |
| Staff Dashboard | `http://localhost:5100/staff-dashboard` |
| Customer Feedback | `http://localhost:5110/review` |
| Staff Feedback Board | `http://localhost:5110/reviews` |
| Menu Management | `http://localhost:5200/menus` |
| Recipe Management | `http://localhost:5200/recipes` |
| Ingredient Management | `http://localhost:5200/ingredients` |
| Customer Menu | `http://localhost:5200/customer-menu` |
| Inventory Dashboard | `http://localhost:5300/inventory/` |
| Inventory Management | `http://localhost:5300/inventory-management` |
| Supplier Management | `http://localhost:5300/supplier-management` |
| Restock Orders | `http://localhost:5300/restock-order-management` |
| POS | `http://localhost:5400/pos` |
| Kitchen Display | `http://localhost:5400/kitchen` |
| Order Status | `http://localhost:5400/status` |
| Payment & Billing | `http://localhost:5500/` |

### Demonstration Accounts

| Role | Email | Password |
|---|---|---|
| Customer | `customer@test.com` | `customer123` |
| Staff | `staff@test.com` | `staff123` |

New customer and staff accounts can also be created through the registration pages.

---

## 8. Feature and AI Integration

### Cross-Feature Integration

Selected features exchange information through APIs.

#### Menu → Order

Student 4 retrieves menu information from Student 2 through the Menu & Recipe backend.

#### Inventory → Order

Student 4 uses Student 3's backend API to check and deduct inventory when processing orders.

Relevant Student 3 endpoints include:

```text
POST /api/inventory/check
POST /api/inventory/deduct
```

#### Order → Payment

Student 5 retrieves order information from Student 4 before processing payments and refunds.

#### Shared Authentication

The shared Flask application handles customer and staff registration and login.

Feature frontends use the shared session when accessing protected areas.

### Release 0 AI Mode

Release 0 introduced feature-specific local AI functionality.

| Feature | AI Capability |
|---|---|
| Student 1 | Feedback sentiment and category analysis |
| Student 2 | Price recommendation explanation |
| Student 3 | Restocking recommendations |
| Student 4 | Kitchen queue and congestion analysis |

Application logic and database data remain authoritative.

The local LLM is used mainly for:

- Analysis
- Explanations
- Recommendations

rather than direct database manipulation.

---

## 9. MCP and RAG Integration

### Shared MCP Server

Release 1 adds one shared MCP server for all student features.

The server:

- Runs locally outside Docker Compose
- Uses the MCP SDK
- Uses Streamable HTTP
- Runs on port `5700`
- Registers feature-specific tools
- Uses feature adapters
- Validates tool arguments
- Returns structured results
- Returns structured errors
- Uses read-only tools

Typical MCP interaction:

```text
Frontend
   ↓
Feature Backend
   ↓
MCP Client
   ↓
Shared MCP Server
   ↓
Registered Tool
   ↓
Feature Adapter
   ↓
Feature Service
```

### Shared RAG Server

The shared RAG server provides retrieval and grounded-response functionality.

It:

- Loads shared and feature-specific knowledge documents
- Splits documents into chunks
- Retrieves and ranks relevant chunks
- Filters low-relevance results
- Sends retrieved context to the local model
- Returns source information
- Returns a confidence category
- Handles insufficient context
- Checks whether the generated response is grounded

Main operations include:

```text
/health
/retrieve
/query
```

Typical RAG flow:

```text
User Question
      ↓
Feature Frontend
      ↓
Feature Backend
      ↓
Shared RAG Server
      ↓
Retrieve Context
      ↓
Relevant Context?
   /             \
 No              Yes
 ↓                ↓
insufficient_    Build Grounded Prompt
context                ↓
                     Ollama
                       ↓
                Grounding Check
                       ↓
                Structured Response
```

A successful response contains information such as:

```json
{
  "answer": "...",
  "confidence": "HIGH",
  "sources": [],
  "success": true
}
```

If suitable project knowledge is unavailable, the server returns an `insufficient_context` response rather than generating an unsupported answer.

---

## 10. Agentic AI Workflow

The project uses the following iterative workflow:

```text
PLAN
  ↓
ACT
  ↓
OBSERVE
  ↓
ADAPT
```

Release 0 introduced this pattern for feature-level review and AI-assisted analysis.

Release 1 extends the shared agentic loop with additional validation modes:

```text
review
mcp
rag
all
```

The modes validate different parts of the system.

### Review Mode

Checks the existing Release 0 implementation and microservice setup.

### MCP Mode

Validates:

- MCP server availability
- Transport/protocol behaviour
- Tool invocation
- Tool responses
- Error handling
- Resilience

### RAG Mode

Validates:

- RAG server availability
- Knowledge retrieval
- Grounding
- Source traceability
- Insufficient-context behaviour
- Resilience

Each validation run records output that can be used for debugging and regression testing.

---

## 11. Testing and CI/CD

### Automated Tests

Each feature contains tests under its own `tests` directory.

Examples:

```bash
python -m pytest student-1/tests -v
python -m pytest student-2/tests -v
python -m pytest student-3/tests -v
python -m pytest student-4/tests -v
python -m pytest student-5/tests -v
```

Some tests require running services, while others use mocks or temporary databases.

### GitHub Actions

CI workflow files are stored in:

```text
.github/workflows/
```

Each student maintains an assigned workflow:

```text
student-1.yml
student-2.yml
student-3.yml
student-4.yml
student-5.yml
```

The workflows validate the corresponding feature's:

- Python source
- Frontend
- Backend/API
- Database service
- Docker configuration
- Automated tests

Release 1 keeps the MCP and RAG integration in the application while keeping the shared MCP and RAG services disabled during normal CI/CD execution.

### Data Persistence

Each feature owns its own SQLite database.

```text
Shared authentication   users.db
Student 1               feedback.db
Student 2               menu_recipe.db
Student 3               inventory.db
Student 4               orders.db
Student 5               payments.db
```

Database services expose data through APIs instead of sharing database files between features.

---

## 12. Team and Release Summary

### Team Responsibilities

| Member | Feature | Release 1 Shared Responsibility |
|---|---|---|
| Hangyeol Yi | Customer Feedback & Reviews | Microservices Integration and Local MCP/RAG Validation |
| Ei Thandar | Menu & Recipe Management | Shared RAG Server and Grounded AI Responses |
| Injeong Yang | Inventory & Restocking | Shared MCP Server |
| Stella Kwon | Order & Kitchen Management | Shared Agentic Loop |
| Ong Ath Vongnathi | Payment & Billing | Docker Compose Integration |

All members also contributed to:

- Maintaining Release 0 functionality
- MCP and RAG integration
- GitHub Actions
- Testing and validation
- Technical report
- Project evidence
- Showcase demonstration

### Release 0

Release 0 established:

- Five cafe-management feature areas
- Frontend, backend/API, and database microservices
- Shared authentication and navigation
- Feature-owned SQLite databases
- HTTP-based cross-feature integration
- Local AI functionality
- Docker Compose deployment
- Automated testing
- Plan → Act → Observe → Adapt workflows

### Release 1

Release 1 extends the application with:

- One shared local MCP server
- Feature-specific registered MCP tools
- Feature adapters
- One shared local RAG server
- Grounded responses with sources and confidence
- Frontend MCP/RAG access through feature backends
- Insufficient-context handling
- Shared MCP and RAG validation modes
- Updated Docker configuration
- Updated GitHub Actions workflows
- Integrated Release 1 validation


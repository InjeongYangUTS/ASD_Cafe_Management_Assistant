# Cafe Management Assistant

41026 Advanced Software Development · Release 0

The Cafe Management Assistant is a containerised microservice application for managing the daily operations of a small cafe. It provides a shared customer/staff entry point and five independently developed feature areas covering feedback, menu and recipes, inventory and restocking, orders and kitchen operations, and payment and billing.

The project uses Flask, SQLite, Docker Compose, GitHub Actions, and local open-source LLMs through Ollama. Each feature is separated into frontend, backend/API, and database responsibilities, and cross-feature communication is performed through HTTP APIs rather than direct access to another feature's database.

---

## 1. Main Features

| Student | Feature | Main capabilities |
|---|---|---|
| Student 1 – Hangyeol Yi | Customer Feedback & Reviews | Customer review CRUD, staff review dashboard, responses, sentiment/category analysis, AI questions over review data, audit logging |
| Student 2 – Ei Thandar | Menu & Recipe Management | Menu CRUD, recipe CRUD, ingredient management, recipe ingredients, customer menu, AI-assisted price recommendation |
| Student 3 – Injeong Yang (Sam) | **Inventory & Restocking | Stock dashboard, inventory CRUD, low/out-of-stock detection, supplier management, restock orders, AI restocking recommendation |
| Student 4 – Stella Kwon | Order & Kitchen Management | POS order placement, kitchen display, order lifecycle/status tracking, inventory integration, AI kitchen queue analysis |
| Student 5 – Ong Ath Vongnathi (Kota) | Payment & Billing | Payment processing, payment records, transaction records, partial/full refunds, refund validation, order integration |

The shared application also provides:

- Customer registration and login
- Staff registration and login
- Customer dashboard
- Staff dashboard
- Shared navigation into the five feature services

---

## 2. Architecture

The Cafe Management Assistant uses a microservices architecture. Each student feature is separated into its own frontend, backend/API, and database services. A shared frontend provides the main entry point for staff and customers, while a shared Ollama service provides AI capabilities across the system.

| Component | Responsibility | Communication |
|---|---|---|
| **Shared Frontend** | Provides the main application entry point, authentication pages, customer dashboard, and staff dashboard. | Redirects users to the appropriate student feature frontend. |
| **Student 1 – Customer Feedback & Reviews** | Manages customer reviews, staff responses, sentiment analysis, and AI-assisted feedback queries. | Frontend communicates with the Student 1 backend/API. Other features can access feedback information through API requests. |
| **Student 2 – Menu & Recipe Management** | Manages menu items, recipes, ingredients, ingredient costs, and AI-assisted price recommendations. | Provides menu and recipe information to other features through its backend API. |
| **Student 3 – Inventory & Restocking** | Manages inventory items, suppliers, stock levels, restock orders, low-stock detection, and AI restocking recommendations. | Uses its backend/API to access its database and communicates with other feature APIs when required. |
| **Student 4 – Order & Kitchen Management** | Handles customer orders, kitchen operations, order status tracking, and AI-assisted kitchen analysis. | Retrieves required menu information through APIs and provides order information to related services. |
| **Student 5 – Payment & Billing Management** | Handles payments, payment records, refunds, partial refunds, and billing-related operations. | Receives order information from Student 4 through API communication and manages payment data through its own backend/database. |
| **Feature Backends / APIs** | Process business logic, CRUD operations, validation, API requests, and communication between microservices. | Communicate with their own database services and other backend services through HTTP APIs. |
| **Feature Databases** | Store data belonging to each individual feature. Each feature owns its own SQLite database. | Accessed only through the backend/API that owns the database. Other features do not directly access another feature's database. |
| **Shared Ollama Service** | Hosts the approved open-source language model used for AI Mode and agentic AI functionality. | Student backend services send prompts and relevant application context to Ollama and receive generated responses. |
| **Docker Compose** | Starts and connects shared services and individual student microservices within one environment. | Provides Docker networking and service configuration for frontend, backend, database, and Ollama containers. |
| **GitHub Actions** | Supports automated testing, validation, and container build checks for project components. | Runs CI workflows based on repository changes and configured workflow files. |

### 2.1 Architecture Principles

| Principle | Description |
|---|---|
| **Feature Separation** | Each student feature is implemented as an independent set of frontend, backend/API, and database components. |
| **Database Ownership** | Each feature owns its database. A feature must not directly read or modify another feature's database. |
| **API-based Integration** | Information required from another feature is retrieved through the owning feature's backend API. |
| **Shared AI Service** | AI-enabled features use the shared Ollama runtime instead of maintaining separate LLM services. |
| **Containerisation** | Project services are containerised and integrated through Docker Compose. |
| **Independent Development** | Each feature can be developed and tested independently before integration into the complete application. |

### 2.2 Architecture rules

1. **Each feature owns its own data.** A feature should not directly open another feature's SQLite database.
2. **Frontend → Backend → Database.** Business logic is handled by backend/API services and persistence by database services.
3. **Cross-feature integration uses HTTP APIs.** For example, Order & Kitchen Management retrieves menu data from Student 2 and checks/deducts stock through Student 3.
4. **AI is local.** AI functions use approved open-source models through Ollama; no cloud LLM API is required for the normal project setup.

---

## 3. Technology Stack

- **Python 3 / Flask** – web applications and REST APIs
- **SQLite** – feature-owned databases
- **HTML / CSS / JavaScript** – user interfaces
- **HTMX** – partial-page interactions in selected features
- **Requests** – service-to-service HTTP communication
- **Docker / Docker Compose** – containerised deployment
- **Ollama** – local LLM runtime
- **Llama 3.2 / Qwen 2.5** – local AI models used by the project
- **Pytest** – automated testing
- **GitHub Actions** – CI workflows

---

## 4. Repository Structure

```text
ASD_Cafe_Management_Assistant/
├── .github/
│   └── workflows/                 GitHub Actions workflows
├── docker/
│   └── shared-frontend.Dockerfile
├── shared/
│   ├── assets/                    Shared icons
│   ├── auth/                      Customer/staff login and registration pages
│   ├── css/                       Shared styling
│   ├── database/                  Shared users database, schema and seed
│   └── frontend/                  Shared entry point and dashboards
├── student-1/
│   ├── frontend/                  Customer/staff feedback UI
│   ├── backend/                   Feedback API and AI logic
│   ├── database/                  Feedback database service
│   ├── prompts/                   Service and agentic prompt assets
│   ├── agentic/                   Agentic workflow logs
│   ├── agentic_loop.py            Plan → Act → Observe → Adapt runner
│   └── tests/
├── student-2/
│   ├── frontend/                  Menu, recipe, ingredient and customer menu UI
│   ├── backend/                   Menu/recipe API and AI pricing logic
│   ├── database/                  Menu and recipe database service
│   └── tests/
├── student-3/
│   ├── frontend/                  Inventory, supplier and restock UI
│   ├── backend/                   Inventory API and agentic AI workflow
│   ├── database/                  Inventory database service
│   ├── assets/                    Feature CSS, JS and icons
│   ├── prompts/
│   └── tests/
├── student-4/
│   ├── frontend/                  POS, kitchen display and order status UI
│   ├── backend/                   Order business logic and AI analysis
│   ├── database/                  Order database service
│   ├── agentic/                   Agentic loop and generated logs
│   ├── prompts/                   Prompt assets
│   ├── evidence/                  Diagrams/screenshots/measurements
│   └── tests/
├── student-5/
│   ├── frontend/                  Payment and refund dashboard
│   ├── backend/                   Payment/refund business logic
│   ├── database/                  Payment database service
│   └── tests/
├── docker-compose.yml
└── README.md
```

---

## 5. Service and Port Map

| Area | Frontend | Backend/API | Database API |
|---|---:|---:|---:|
| Shared authentication/dashboard | **5100** | – | internal `users.db` |
| Student 1 – Feedback & Reviews | **5110** | **8100** | **7100** |
| Student 2 – Menu & Recipe | **5200** | **5201** | **5202** |
| Student 3 – Inventory & Restocking | **5300** | **8300** | **7300** |
| Student 4 – Order & Kitchen | **5400** | **8400** | **7400** |
| Student 5 – Payment & Billing | **5500** | **8500** | **7500** |
| Ollama | – | **11434** | – |

---

## 6. Quick Start with Docker Compose

### Prerequisites

Install:

- Git
- Docker Desktop / Docker Engine with Docker Compose

The first AI-enabled startup may take longer because Ollama must download the configured models.

### Clone the repository

```bash
git clone https://github.com/InjeongYangUTS/ASD_Cafe_Management_Assistant.git
cd ASD_Cafe_Management_Assistant
```

### Start the complete application

From the repository root:

```bash
docker compose up --build
```

To run in the background:

```bash
docker compose up --build -d
```

Check service state:

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

To also remove project volumes:

```bash
docker compose down -v
```

> Removing volumes deletes data stored in Docker volumes and causes seeded data to be recreated on a later fresh startup.

---

## 7. Opening the Application

After the services are running, open:

**http://localhost:5100**

The shared home page provides access to customer and staff login pages. After login, the appropriate dashboard links to the feature services.

### Demonstration accounts

| Role | Email | Password |
|---|---|---|
| Customer | `customer@test.com` | `customer123` |
| Staff | `staff@test.com` | `staff123` |

New customer and staff accounts can also be created through the registration pages.

---

## 8. Main User Interfaces

| Feature | URL |
|---|---|
| Shared home | `http://localhost:5100/` |
| Customer dashboard | `http://localhost:5100/customer-dashboard` |
| Staff dashboard | `http://localhost:5100/staff-dashboard` |
| Customer Feedback | `http://localhost:5110/review` |
| Staff Feedback Board | `http://localhost:5110/reviews` |
| Menu Management | `http://localhost:5200/menus` |
| Recipe Management | `http://localhost:5200/recipes` |
| Ingredient Management | `http://localhost:5200/ingredients` |
| Customer Menu | `http://localhost:5200/customer-menu` |
| Inventory Dashboard | `http://localhost:5300/inventory/` |
| Inventory Management | `http://localhost:5300/inventory-management` |
| Supplier Management | `http://localhost:5300/supplier-management` |
| Restock Order Management | `http://localhost:5300/restock-order-management` |
| POS / Order Placement | `http://localhost:5400/pos` |
| Kitchen Display | `http://localhost:5400/kitchen` |
| Order Status | `http://localhost:5400/status` |
| Payment & Billing | `http://localhost:5500/` |

---

## 9. Feature Integration

The project is intentionally divided into independent service boundaries, but selected features exchange data through APIs.

### Shared authentication

The shared Flask service owns customer and staff registration/login. Feature frontends that need the authenticated session use the same Flask secret key/session mechanism so the browser can carry the login state between ports on the same host.

### Menu → Order

Student 4 retrieves menu information from Student 2 rather than copying or directly querying Student 2's database.

### Inventory → Order

Student 4 uses Student 3's backend API to:

- check whether sufficient inventory exists before an order is accepted;
- deduct inventory when appropriate.

Relevant Student 3 endpoints include:

```text
POST /api/inventory/check
POST /api/inventory/deduct
```

### Order → Payment

Student 5 retrieves order information from Student 4, checks the order total/status, records payment, and can request an order status update after successful payment.

### Order/Menu → Feedback

Student 1 can use order/menu context exposed through peer APIs when connecting reviews to cafe activity, while its own review records remain inside the Student 1 database boundary.

---

## 10. AI Mode

AI-assisted functionality is implemented as part of the normal application rather than as a separate standalone chatbot.

| Feature | AI capability |
|---|---|
| Student 1 | Review sentiment/category analysis and staff questions over feedback data |
| Student 2 | Menu price recommendation explanation based on deterministic pricing calculations |
| Student 3 | Restocking recommendations based on actual low/out-of-stock inventory data |
| Student 4 | Kitchen queue analysis, congestion assessment and preparation priority |

The Compose configuration includes a shared Ollama service and an initialisation service that pulls the configured models. The default Compose model is `llama3.2`, while `qwen2.5:0.5b` is also pulled for workflows that use it.

```text
Frontend
   |
   v
Backend/API
   |---- deterministic application/database context
   |
   v
Ollama / local LLM
   |
   v
Backend validation / response formatting
   |
   v
Frontend
```

The project generally keeps calculations and authoritative application data in Python/database logic and uses the LLM for analysis, explanation or recommendation on top of that data.

> Student 2's current AI pricing implementation calls `host.docker.internal:11434`, so Docker Desktop users should also ensure Ollama is reachable from the host at that address when demonstrating that specific AI function.

---

## 11. Agentic AI Workflow

The project uses the **Plan → Act → Observe → Adapt** workflow as an iterative review and decision pattern.

```text
PLAN
  Decide what should be checked or analysed.
    |
    v
ACT
  Perform the selected checks/actions.
    |
    v
OBSERVE
  Compare results with expected behaviour and evidence.
    |
    v
ADAPT
  Correct the recommendation or choose the next action.
```

Examples implemented in the repository include:

### Student 1

```bash
python student-1/agentic_loop.py
```

Useful non-interactive modes:

```bash
python student-1/agentic_loop.py --no-input
python student-1/agentic_loop.py --no-ai
```

The loop checks areas such as data quality, service availability, performance/NFR evidence and AI behaviour, and writes workflow records under `student-1/agentic/logs/`.

### Student 3

With the Student 3 backend and Ollama available:

```bash
python student-3/backend/agentic_inventory.py
```

The inventory agent retrieves low-stock data and performs Plan, Act, Observe and Adapt steps before generating the final restocking priority. Generated JSON logs are written to the configured Student 3 log directory.

### Student 4

```bash
python student-4/agentic/loop.py
```

The Student 4 loop probes the implementation and running services, records observations, and adapts the next focus. Workflow logs are stored under `student-4/agentic/logs/`.

---

## 12. API Overview

This section lists the main integration-facing endpoints. Individual feature READMEs and source files contain the full endpoint set.

### Student 1 – Feedback & Reviews (`:8100`)

```text
GET    /api/health
GET    /api/feedback
POST   /api/feedback
GET    /api/feedback/<id>
PUT    /api/feedback/<id>
DELETE /api/feedback/<id>
GET    /api/summary
POST   /api/ai/ask
POST   /api/ai/analyse/<id>
POST   /api/ai/analyse-pending
```

### Student 2 – Menu & Recipe (`:5201`)

```text
GET/POST        /api/menus
GET/PUT/DELETE  /api/menus/<id>
GET/POST        /api/ingredients
GET/POST        /api/recipes
GET              /api/ai/price-recommendation/<menu_id>
```

### Student 3 – Inventory & Restocking (`:8300`)

```text
GET              /api/health
GET               /api/dashboard
GET/POST          /api/inventory
GET/PUT/DELETE    /api/inventory/<id>
POST              /api/inventory/check
POST              /api/inventory/deduct
GET/POST          /api/suppliers
GET/PUT/DELETE    /api/suppliers/<id>
GET/POST          /api/restock-orders
GET/PUT/DELETE    /api/restock-orders/<id>
POST              /api/ai/restock-recommendation
```

### Student 4 – Order & Kitchen (`:8400`)

```text
GET               /api/health
GET               /api/menu
GET/POST          /api/orders
GET/PUT/DELETE    /api/orders/<id>
GET               /api/order-status
GET/PUT           /api/order-status/<id>
GET               /api/kitchen/queue
POST              /api/ai/kitchen-analysis
```

### Student 5 – Payment & Billing (`:8500`)

```text
GET    /health
GET    /api/payments
GET    /api/payments/<id>
POST   /api/payments/process
GET    /api/refunds
POST   /api/refunds
```

---

## 13. Running Individual Feature Stacks

For faster development, individual services can be started without bringing up every feature.

### Student 1

```bash
docker compose up --build student-1-database student-1-backend student-1-frontend
```

### Student 2

```bash
docker compose up --build student2-database student2-backend student2-frontend
```

### Student 3

```bash
docker compose up --build student-3-database student-3-backend student-3-frontend
```

### Student 4

```bash
docker compose up --build student-4-database student-4-backend student-4-frontend
```

### Student 5

```bash
docker compose up --build student-5-database student-5-backend student-5-frontend
```

When testing cross-feature integration, also start the peer services required by that feature.

---

## 14. Tests

Each student feature contains its own automated tests under `student-N/tests/`.

Examples:

```bash
python -m pytest student-1/tests -v
python -m pytest student-2/tests -v
python -m pytest student-3/tests -v
python -m pytest student-4/tests -v
python -m pytest student-5/tests -v
```

Some integration/smoke tests expect running services, while unit tests may use mocks or temporary databases. Refer to the feature-specific README before running a feature's full test suite.

---

## 15. CI/CD

GitHub Actions workflow files are stored in:

```text
.github/workflows/
```

The repository currently includes workflow definitions for Student 1 and Student 2, while `student-4.yml` is present but empty in the submitted project snapshot.

Implemented CI activities include combinations of:

- Python compilation/syntax checks
- dependency installation
- Pytest execution
- database validation
- Docker Compose configuration validation
- Docker image builds
- service smoke tests
- agentic-loop evidence generation

---

## 16. Data Persistence

Each feature owns its own SQLite data store. Database services expose HTTP APIs to the other layers rather than sharing `.db` files directly.

Examples include:

- Shared authentication: `users.db`
- Student 1: `feedback.db`
- Student 2: `menu_recipe.db`
- Student 3: `inventory.db`
- Student 4: `orders.db`
- Student 5: `payments.db`

Docker volumes are used for selected services in `docker-compose.yml` to preserve application data between container restarts.

---

## 17. Known Limitations

This repository is a **Release 0 university prototype**, not a production deployment. Current limitations include:

- SQLite is used for simplicity and local development.
- Authentication is implemented through the shared Flask application and is not uniformly enforced at every backend boundary.
- Payment processing is simulated and does not connect to a real payment gateway.
- AI features depend on a locally available Ollama runtime and downloaded models.
- Some feature integrations include fallbacks or graceful degradation when another service is unavailable.
- Student 2 currently reaches Ollama through `host.docker.internal` rather than the shared `ollama` service name.
- CI coverage differs between student features in the current repository snapshot.

---

## 18. Team

- **Hangyeol Yi** — Customer Feedback & Reviews
- **Ei Thandar** — Menu & Recipe Management
- **Injeong Yang (Sam)** — Inventory & Restocking
- **Stella Kwon** — Order & Kitchen Management
- **Ong Ath Vongnathi (Kota)** — Payment & Billing

---

## 19. Release

**Release 0** demonstrates the integrated foundation of the Cafe Management Assistant: containerised feature services, database-backed CRUD operations, shared authentication/navigation, inter-service API communication, local AI-assisted functionality, automated testing, and agentic Plan → Act → Observe → Adapt workflows.

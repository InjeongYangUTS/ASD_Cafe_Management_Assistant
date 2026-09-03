# Student 3 Inventory Service

## Ports

| Service | Port | Address |
|---|---:|---|
| Frontend | 5300 | `http://127.0.0.1:5300/inventory/` |
| Backend API | 8300 | `http://127.0.0.1:8300/api/health` |
| Database API | 7300 | `http://127.0.0.1:7300/db/health` |

## Docker Compose

Run the following command from the project root after starting Docker Desktop.

```powershell
docker compose up --build -d shared-frontend student-3-database student-3-backend student-3-frontend
```

Check the services.

```powershell
docker compose ps
docker compose logs --tail=100 student-3-database student-3-backend student-3-frontend
```

Open `http://127.0.0.1:5100/staff-dashboard` and select the Inventory card, or open `http://127.0.0.1:5300/inventory/` directly.

Stop the services.

```powershell
docker compose stop shared-frontend student-3-database student-3-backend student-3-frontend
```

## Service Flow

The browser connects to the frontend on port 5300. The frontend calls the backend on port 8300. The backend calls the database service on port 7300. Only the database service accesses SQLite.

## API

The backend provides inventory, supplier, restock order, inventory availability, inventory deduction and AI restocking endpoints under `/api`.

The database service provides internal persistence endpoints under `/db`.

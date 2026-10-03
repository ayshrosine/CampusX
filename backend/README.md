# AssetFlow Campus — Backend

A **FastAPI** service (Python 3.11) backed by **MongoDB** (via the async **Motor**
driver). It exposes a JSON API under the `/api` prefix, enforces cookie-based
authentication and server-side role-based access control (RBAC), and integrates
Cloudinary (uploads), ReportLab (PDF), and Web Push (VAPID).

---

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Authentication](#authentication)
- [Roles & Permissions (RBAC)](#roles--permissions-rbac)
- [API Endpoints](#api-endpoints)
- [Data Model](#data-model)
- [Local Development Setup](#local-development-setup)
- [External Services Configuration](#external-services-configuration)
- [Environment Variables](#environment-variables)
- [Integrations](#integrations)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## 1. Architecture Overview

```
Client (React SPA)
   │  fetch  https://<backend>/api/...   (withCredentials → session_token cookie)
   ▼
FastAPI app  (server.py)
   ├── APIRouter(prefix="/api")            # every route is /api/*
   ├── current_user  dependency           # validates session cookie/Bearer token
   ├── require_permission(perm) dependency # RBAC gate → 403 if not allowed
   ├── log_event()                         # writes to `activity` audit log
   ├── Integrations: Cloudinary · ReportLab · pywebpush
   └── startup: idempotent seed()
   ▼
MongoDB (Motor, async)  — DB name from env DB_NAME
```

- **Single-file design:** `server.py` (~875 lines) contains Pydantic models, helpers,
  RBAC tables, all route handlers, integration code and the seed routine.
- **IDs:** all documents use string **UUIDs** (`user_id`, `asset_id`, …). MongoDB
  `_id` is stripped from every response via `clean()` (never exposed).
- **CORS:** driven by `CORS_ORIGINS` env; cookies are `SameSite=None; Secure; HttpOnly`.
- Runs on **0.0.0.0:8001** under Supervisor; Kubernetes ingress maps `/api` here.

---

## 2. Authentication

- **Sessions:** `create_session()` issues a random `secrets.token_urlsafe(32)` token
  stored in `user_sessions` with a 7-day expiry; returned as an httpOnly cookie.
- **`current_user`** reads the cookie (or `Authorization: Bearer`), validates the
  session + expiry, loads the user, and applies any **active delegation** (see RBAC).
- **Password auth:** `bcrypt` hashing (`bcrypt.hashpw` / `checkpw`); passwords are
  never returned (`password_hash` filtered out).
- **Google OAuth:** `POST /api/auth/session` exchanges an Emergent-managed
  `X-Session-ID` (validated against `demobackend.emergentagent.com`) for a local
  session. New Google users are created as **Student / Pending**.

---

## 3. Roles & Permissions (RBAC)

```python
ROLES = {"Admin", "Asset Manager", "HOD", "Employee", "Student"}

ROLE_PERMISSIONS = {
  "Admin":         {"admin","asset_write","maintenance_write","booking","audit","nodues","reports"},
  "Asset Manager": {"asset_write","maintenance_write","booking","audit","reports"},
  "HOD":           {"asset_write","maintenance_write","booking","reports"},
  "Employee":      {"maintenance_write","booking","reports"},
  "Student":       {"booking","maintenance_write"},
}
```

- `require_permission("x")` is a FastAPI dependency injected into protected routes;
  it raises **403** if the caller's role lacks the permission.
- **Delegation:** in `current_user`, if a `delegations` record has the caller as
  `deputy_id` and the current time is inside `[start_at, end_at]` with status
  `Scheduled`, the user's role is temporarily elevated to **Admin** for that request.
- Guardrails: signup always creates **Student/Pending**; an Admin cannot demote
  themselves out of Admin.

---

## 4. API Endpoints

All under `/api`. "Perm" is the permission checked (blank = any authenticated user).

### Auth
| Method | Path | Perm | Description |
|---|---|---|---|
| GET  | `/` | — | Health/info |
| POST | `/auth/signup` | — | Create account (Student/Pending) |
| POST | `/auth/login` | — | Email/password login → session cookie |
| GET  | `/auth/me` | auth | Current user profile |
| POST | `/auth/session` | — | Exchange Google/Emergent session id |
| POST | `/auth/logout` | auth | Clear session |

### Dashboard / Activity
| GET | `/dashboard` | auth | KPIs + recent activity |
| GET | `/activity` | auth | Full audit log (latest 200) |

### Assets
| GET   | `/assets` | auth | List (search, status, category filters) |
| POST  | `/assets` | asset_write | Create asset |
| GET   | `/assets/{asset_id}` | auth | Asset detail |
| PATCH | `/assets/{asset_id}` | asset_write | Update asset |
| POST  | `/assets/{asset_id}/checkout` | auth | Allocate to holder |
| POST  | `/assets/{asset_id}/checkin` | auth | Return |
| GET   | `/assets/by-tag/{tag}` | auth | Lookup by QR/tag (scan flow) |

### Maintenance
| GET    | `/maintenance` | auth | Board data (grouped by stage) |
| POST   | `/maintenance` | maintenance_write | Raise work order (push to Admin/AM/HOD if high) |
| PATCH  | `/maintenance/{request_id}` | maintenance_write | Move stage / resolve / reject |
| DELETE | `/maintenance/{request_id}` | maintenance_write | Delete (owner or Admin/AM/HOD) |
| POST   | `/maintenance/{request_id}/photos` | maintenance_write | Attach Cloudinary photo |
| DELETE | `/maintenance/{request_id}/photos/{public_id}` | maintenance_write | Remove photo |

> Resolved work orders are **auto-deleted 30 days** after resolution.

### Bookings
| GET    | `/bookings` | auth | List bookings |
| POST   | `/bookings` | booking | Create booking |
| DELETE | `/bookings/{booking_id}` | booking | Cancel |

### Audits
| GET   | `/audits` | audit | List audits |
| POST  | `/audits` | audit | Start audit run |
| PATCH | `/audits/{audit_id}/items/{asset_id}` | audit | Set item condition |
| POST  | `/audits/{audit_id}/items/{asset_id}/photos` | audit | Attach evidence |
| POST  | `/audits/{audit_id}/close` | audit | Close audit |
| GET   | `/audits/{audit_id}/pdf` | audit | Closed-audit PDF |

### No-Dues
| GET   | `/nodues` | nodues | Student clearance list (Admin only) |
| PATCH | `/nodues/{student_id}/{department}` | nodues | Update a department status |

### Reports & Digest
| GET | `/reports` | reports | Operational report |
| GET | `/reports/accreditation` | reports | NAAC/NBA report data |
| GET | `/reports/accreditation/download` | reports | Signed PDF / CSV export |
| GET | `/digest/weekly` | reports | Weekly digest (admin view) |

### Notifications & Push
| GET  | `/notifications` | auth | Notification feed |
| POST | `/notifications/mark-all-read` | auth | Mark read |
| GET  | `/push/public-key` | auth | VAPID public key |
| POST | `/push/subscribe` | auth | Store push subscription |
| POST | `/push/unsubscribe` | auth | Remove subscription |

### Admin
| GET/POST | `/admin/departments` | admin | List / create departments |
| GET/POST | `/admin/categories` | admin | List / create categories |
| GET   | `/admin/users` | admin | List users |
| PATCH | `/admin/users/{user_id}/role` | admin | Change role/status |
| GET   | `/admin/role-preview/{role}` | admin | Role playground preview |
| GET/PUT | `/admin/branding` | admin | Institution cover-sheet/branding |
| GET/POST | `/admin/delegations` | admin | List / create delegation slots |
| DELETE | `/admin/delegations/{delegation_id}` | admin | Revoke delegation |
| POST  | `/admin/imports/{kind}` | admin | Bulk CSV import (e.g. assets/users) |

---

## 5. Data Model (MongoDB collections)

| Collection | Key fields |
|---|---|
| `users` | user_id, name, email, role, department, status, password_hash, picture |
| `user_sessions` | user_id, session_token, created_at, expires_at |
| `assets` | asset_id, tag, name, category, location, department, status, serial, bookable, holder |
| `maintenance` | request_id, asset_id, description, priority, status, raised_by, photos[], created_at |
| `bookings` | booking_id, asset_id, user, start/end window |
| `audits` | audit_id, items[{asset_id, condition, photos[]}], status |
| `nodues` | student_id, student_name, roll_number, overall_status, department_statuses[] |
| `activity` | event_id, actor, action, entity_type, entity_id, before, after, timestamp |
| `departments` | department_id, name, type, head, status |
| `categories` | category_id, name, example_items, warranty_tracked, amc_tracked |
| `branding` | institution name, tagline, accreditation body, footer, accent colour, logo |
| `delegations` | delegation_id, admin_id/name, deputy_id, start_at, end_at, status |
| `push_subs` | subscription endpoint + keys per user |
| `notification_state` | per-user read markers |

---

## 6. Local Development Setup

### Prerequisites

- **Python 3.11** - [Download here](https://www.python.org/downloads/)
- **MongoDB** (local or MongoDB Atlas account)
- **pip** (Python package manager)

### Step-by-Step Setup

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Create a `.env` file by copying the example file:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` with your actual credentials (see [Environment Variables](#environment-variables) section)

5. **Start the development server:**
   ```bash
   uvicorn server:app --reload --host 0.0.0.0 --port 8001
   ```

6. **Verify the server is running:**
   ```bash
   curl http://localhost:8001/api/
   ```

The backend will be available at `http://localhost:8001` with the API prefixed by `/api`.

### Development Tools

**Code Formatting:**
```bash
# Format code with Black
black server.py

# Sort imports with isort
isort server.py
```

**Linting:**
```bash
# Lint with flake8
flake8 server.py

# Type checking with mypy
mypy server.py
```

---

## 7. External Services Configuration

The backend requires several external services to function properly:

### MongoDB Atlas

1. **Create a MongoDB Atlas account** at [https://www.mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)
2. **Create a cluster** (free tier available)
3. **Configure network access** - add your IP to the IP whitelist
4. **Create a database user** with read/write permissions
5. **Get the connection string** from the Connect dialog
6. **Update your `.env` file** with the connection string

### Cloudinary

1. **Create a Cloudinary account** at [https://cloudinary.com/](https://cloudinary.com/)
2. **Navigate to the Dashboard** to get your credentials:
   - Cloud Name
   - API Key
   - API Secret
3. **Configure upload settings** (optional) in the Cloudinary console
4. **Update your `.env` file** with the Cloudinary credentials

### Web Push (VAPID)

1. **Generate VAPID keys** using:
   ```bash
   npx web-push generate-vapid-keys
   ```
   Or use the online generator: [https://web-push-codelab.glitch.me/](https://web-push-codelab.glitch.me/)

2. **Update your `.env` file** with the VAPID keys

### Google OAuth (via Emergent)

1. **Create a Google Cloud Project** at [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. **Enable the Google+ API**
3. **Configure OAuth consent screen**
4. **Create OAuth 2.0 credentials**
5. **Configure with Emergent service** to manage the OAuth flow

---

## 8. Environment Variables

Create a `.env` file in the backend directory by copying the example file:
```bash
cp .env.example .env
```
Then edit `.env` with your actual credentials. The example file contains all the required variables with placeholder values.

**Required Variables:**
- `MONGO_URL` - MongoDB Atlas connection string
- `DB_NAME` - Database name
- `CLOUDINARY_CLOUD_NAME` - Cloudinary cloud name
- `CLOUDINARY_API_KEY` - Cloudinary API key
- `CLOUDINARY_API_SECRET` - Cloudinary API secret
- `VAPID_PUBLIC_KEY` - VAPID public key for push notifications
- `VAPID_PRIVATE_KEY` - VAPID private key for push notifications
- `VAPID_SUBJECT` - VAPID subject (email)
- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `GOOGLE_CLIENT_SECRET` - Google OAuth client secret

**Important Notes:**
- Never commit the `.env` file to version control
- Use strong, unique passwords for MongoDB
- Keep API secrets secure and rotate them regularly
- In production, use environment-specific configurations

---

## 9. Integrations

- **Cloudinary** — the client requests a short-lived upload **signature** from
  `GET /api/uploads/signature`, uploads the file directly to Cloudinary, then posts
  the resulting `public_id`/URL back to the relevant `*/photos` endpoint. RBAC controls
  who may delete a photo (owner or manager roles). Config via `CLOUDINARY_*` env.
- **ReportLab** — server-side PDF generation for the NAAC/NBA accreditation report
  (uses the admin-edited branding cover sheet + accent colour), closed-audit PDFs, and
  the weekly digest.
- **Web Push (VAPID)** — `pywebpush` sends browser notifications (e.g. high-priority
  maintenance). Keys via `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT`.

---

## 10. Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=server

# Run specific test file
pytest tests/test_specific.py

# Run with verbose output
pytest -v
```

### Test Structure

- **Unit tests**: Test individual functions and components
- **Integration tests**: Test API endpoints and database interactions
- **Authentication tests**: Verify session management and RBAC

### Test Files

- `tests/test_assetflow_api.py` - Main backend test suite
- `tests/test_new_features.py` - Tests for new features

### Key Dependencies

- `pytest` - Testing framework
- `pytest-xdist` - Parallel test execution
- `pytest-cov` - Coverage reporting

---

## 11. Deployment

### Production Deployment

The backend is designed to run in production environments using:

1. **Supervisor** (recommended for production)
2. **Kubernetes** (for containerized deployments)
3. **Docker** (for containerization)

### Supervisor Configuration

Example supervisor configuration:

```ini
[program:backend]
command=/path/to/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001
directory=/path/to/backend
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/supervisor/backend.log
environment=ENV_VAR="value"
```

**Commands:**
```bash
# Restart backend service
sudo supervisorctl restart backend

# Check status
sudo supervisorctl status backend

# View logs
tail -f /var/log/supervisor/backend.log
```

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
```

**Build and run:**
```bash
docker build -t assetflow-backend .
docker run -p 8001:8001 --env-file .env assetflow-backend
```

### Environment-Specific Considerations

- **Production**: Use production MongoDB Atlas cluster, secure API keys, enable HTTPS
- **Staging**: Use staging environment for testing before production deployment
- **Development**: Use local MongoDB or development Atlas cluster

---

## 12. Troubleshooting

### Common Issues

**Connection to MongoDB failed:**
- Verify `MONGO_URL` is correct in `.env`
- Check MongoDB Atlas IP whitelist includes your server IP
- Ensure database user has correct permissions
- Check network connectivity to MongoDB Atlas

**Cloudinary upload errors:**
- Verify Cloudinary credentials are correct
- Check Cloudinary account status and limits
- Ensure upload presets are properly configured
- Check file size limits and supported formats

**Push notifications not working:**
- Verify VAPID keys are correctly configured
- Check browser supports Web Push API
- Ensure service worker is properly registered
- Check push subscription is valid

**Authentication failures:**
- Verify session cookie is being sent
- Check session expiration settings
- Ensure `current_user` dependency is working
- Verify RBAC permissions are correctly configured

**PDF generation errors:**
- Check ReportLab installation
- Verify font availability
- Check branding configuration
- Ensure sufficient memory for PDF generation

### Debug Mode

Enable debug mode for detailed error messages:

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8001 --log-level debug
```

### Log Files

- **Supervisor logs**: `/var/log/supervisor/backend.log`
- **Application logs**: Configure logging in `server.py`
- **Error logs**: Check both application and supervisor logs

---

## Key Dependencies

The backend uses the following key libraries (see `requirements.txt` for full list):

- `fastapi` - Modern web framework for building APIs
- `uvicorn` - ASGI server for running FastAPI
- `motor` - Async MongoDB driver
- `pydantic` - Data validation and settings management
- `bcrypt` - Password hashing
- `cloudinary` - Cloud image and video management
- `reportlab` - PDF generation
- `pywebpush` - Web Push notification support
- `python-dotenv` - Environment variable management
- `google-auth` - Google OAuth authentication
- `requests` - HTTP library for making requests

---

## Seeding

A comprehensive, realistic demo dataset is provided in `backend/seed_data.py` (and automatically invoked on backend startup if the database has fewer than 50 assets):

- **260 Assets**: Spanning 10 categories, 15 campus departments, and all operational statuses (`Available`, `Allocated`, `Under Maintenance`, `Lost`, `Retired`), bookable equipment and facilities, financial records, warranties, and suppliers.
- **50 Maintenance Requests**: Spanning `Pending`, `Approved`, `In progress`, `Resolved`, and `Rejected` statuses across `High`, `Medium`, and `Low` priorities.
- **45 Bookings**: Past history, today's schedule, and upcoming 7-day calendar reservations for rooms, buses, laptops, projectors, and labs.
- **12 Audit Cycles**: 5 Open cycles and 7 Closed cycles with item verifications (`Verified`, `Missing`, `Damaged`, `Pending`) and photo evidence.
- **35 Student No-Dues Clearances**: Clearances across Library, Hostel, Sports, Laboratory, and Accounts (`Cleared`, `In progress`, `Pending`).
- **300 Activity Logs**: Full 30-day chronological audit trail across alerts, approvals, bookings, and asset mutations.
- **28 Demo Users**: Across `Admin`, `Asset Manager`, `HOD`, `Employee`, and `Student` roles.
- **15 Campus Departments & 10 Asset Categories**.
- **8 Custom Report Templates & 6 Administrative Delegations**.

### Running the Seed Script Manually

```bash
cd backend
python seed_data.py
```

To preserve existing data without dropping:
```bash
python seed_data.py --keep
```

An admin can also trigger a complete seed refresh directly via `POST /api/admin/seed` or from the Admin Console UI.

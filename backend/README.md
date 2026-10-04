# AssetFlow Campus — Backend Service

A high-performance asynchronous **FastAPI** service (Python 3.11) backed by **MongoDB Atlas** via the async **Motor** driver. It provides a RESTful JSON API under the `/api` prefix, enforces HTTP-only cookie-based session authentication and server-side Role-Based Access Control (RBAC), and manages integrations with Cloudinary (signed photo uploads), ReportLab (compliance PDF generation), and Web Push (VAPID push notifications).

---

## 📋 Table of Contents

- [Architecture & Design Decisions](#architecture--design-decisions)
- [Archify Architecture Specifications](#archify-architecture-specifications)
- [Directory Layout](#directory-layout)
- [Authentication & Session Lifecycle](#authentication--session-lifecycle)
- [Roles & Permissions (RBAC)](#roles--permissions-rbac)
- [API Endpoints Reference](#api-endpoints-reference)
- [Data Model & MongoDB Collections](#data-model--mongodb-collections)
- [Demo Dataset & Seeding](#demo-dataset--seeding)
- [External Integrations](#external-integrations)
- [Local Setup & Development](#local-setup--development)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Deployment](#deployment)
- [Troubleshooting & FAQ](#troubleshooting--faq)

---

## 🏛 Architecture & Design Decisions

```
Client (React SPA / Mobile PWA)
   │  fetch https://<host>/api/... (withCredentials: true ➔ session_token cookie)
   ▼
FastAPI Application (server.py)
   ├── APIRouter(prefix="/api")             # All application routes prefixed with /api
   ├── current_user dependency              # Validates session cookie or Bearer token
   ├── require_permission(perm) dependency  # Server-side RBAC guard ➔ 403 on forbidden
   ├── log_event()                          # Writes immutable records to `activity` log
   ├── Integrations Engine                  # Cloudinary, ReportLab, pywebpush
   └── Seed Data Runner                     # Automatic initialization of realistic campus data
   ▼
MongoDB Atlas (Async Motor Driver)          # Database collections (UUID primary keys)
```

- **UUID Primary Keys**: All entities use domain-prefixed string UUIDs (e.g. `ast_...`, `user_...`, `req_...`, `bk_...`). MongoDB internal `_id` values are stripped from API outputs via the `clean()` helper to prevent schema leakage.
- **Strict Pydantic Validation**: Models enforce length constraints and disallow whitespace-only strings via field validators.
- **Dynamic Admin Delegation**: Supports scheduled, time-windowed delegation slots allowing administrators to elevate deputies temporarily.
- **Audit Logging by Design**: Every state-altering endpoint invokes `log_event()` to maintain a permanent chronological trail in the `activity` collection.

---

## 📐 Archify Architecture Specifications

The system's architectural layers and behaviors are formalized in the root `docs/architecture/` suite:

1. **[System Architecture](file:///d:/projects/CampusX/docs/architecture/system-architecture.html)** (`system-architecture.architecture.json`): Maps the 8–12 core components across Client, Application, and Cloud boundaries.
2. **[Maintenance Workflow](file:///d:/projects/CampusX/docs/architecture/maintenance-workflow.html)** (`maintenance-workflow.workflow.json`): Models triage, approval gates, technician evidence upload, and 30-day auto-expiry.
3. **[QR Checkout Sequence](file:///d:/projects/CampusX/docs/architecture/qr-checkout.html)** (`qr-checkout.sequence.json`): Traces the field scan, RBAC check, atomic status mutation, and non-blocking audit side effect.
4. **[Asset Dataflow](file:///d:/projects/CampusX/docs/architecture/asset-dataflow.html)** (`asset-dataflow.dataflow.json`): Details the 5-stage data journey from ingestion to NAAC/NBA accreditation reports.
5. **[Asset Lifecycle](file:///d:/projects/CampusX/docs/architecture/asset-lifecycle.html)** (`asset-lifecycle.lifecycle.json`): Full operational state machine separating active, waiting, recovery, and terminal states.

---

## 📁 Directory Layout

```
backend/
├── server.py             # Main FastAPI service: routes, models, RBAC, and integrations
├── seed_data.py          # Standalone seed script generating 260 assets and campus records
├── requirements.txt      # Python dependencies
├── pytest.ini            # Pytest execution configuration
├── .env.example          # Environment variable template
├── .env                  # Local secret configuration (git-ignored)
└── tests/                # Automated test suite
    ├── test_assetflow_api.py # Core API and RBAC test suite
    └── test_new_features.py  # Validation for push notifications, QR, and digest
```

---

## 🔐 Authentication & Session Lifecycle

- **Session Cookies**: Upon successful login, the server generates a cryptographically secure random token (`secrets.token_urlsafe(32)`), persists it in `user_sessions` with a 7-day TTL, and issues an `HttpOnly; SameSite=None; Secure` cookie named `session_token`.
- **Password Security**: Passwords are authenticated and hashed using `bcrypt` with unique salts. Password hashes are excluded from all API responses.
- **Google OAuth**: Clients send a Google ID token to `POST /api/auth/session`. The server validates the token against Google OAuth servers using `google-auth`. New users default to the **Student** role with `Pending` status until reviewed by an Admin.
- **Session Identification**: The `current_user` dependency resolves the caller from the cookie or `Authorization: Bearer` header, checks expiration, and applies active delegation slots.

---

## 🛡 Roles & Permissions (RBAC)

```python
ROLES = {"Admin", "Asset Manager", "HOD", "Employee", "Student"}

ROLE_PERMISSIONS = {
    "Admin":         {"admin", "asset_write", "maintenance_write", "booking", "audit", "nodues", "reports"},
    "Asset Manager": {"asset_write", "maintenance_write", "booking", "audit", "reports"},
    "HOD":           {"asset_write", "maintenance_write", "booking", "reports"},
    "Employee":      {"maintenance_write", "booking", "reports"},
    "Student":       {"booking", "maintenance_write"},
}
```

- Injected via `Depends(require_permission("permission_name"))`.
- Forbidden operations raise HTTP `403 Forbidden`.
- An Admin cannot demote themselves or revoke their own admin permissions to protect system accessibility.

---

## 🔌 API Endpoints Reference

All endpoints reside under the `/api` prefix.

### Authentication & Account
| Method | Route | Permission | Description |
|---|---|---|---|
| `GET` | `/` | Open | Health check & API version information |
| `POST` | `/auth/signup` | Open | Register new account (Student / Pending) |
| `POST` | `/auth/login` | Open | Authenticate via email & password |
| `GET` | `/auth/me` | Authenticated | Fetch current user session profile |
| `PATCH`| `/auth/profile` | Authenticated | Update user display name, phone, department |
| `POST` | `/auth/session` | Open | Exchange Google OAuth ID token for session |
| `POST` | `/auth/logout` | Authenticated | Invalidate session token & clear cookie |

### Dashboard & Inventory
| Method | Route | Permission | Description |
|---|---|---|---|
| `GET` | `/dashboard` | Authenticated | Overview KPIs, asset counts, live activity feed |
| `GET` | `/activity` | Authenticated | Chronological audit trail (filters for alerts, bookings, approvals) |
| `GET` | `/assets` | Authenticated | Filterable asset catalog (status, category, search) |
| `POST`| `/assets` | `asset_write` | Register new campus asset |
| `GET` | `/assets/{asset_id}` | Authenticated | Retrieve complete asset specifications |
| `PATCH`| `/assets/{asset_id}` | `asset_write` | Update asset details, location, status |
| `POST`| `/assets/{asset_id}/checkout` | Authenticated | Allocate asset to a student or staff holder |
| `POST`| `/assets/{asset_id}/checkin` | Authenticated | Process return of an allocated asset |
| `GET` | `/assets/by-tag/{tag}` | Authenticated | Rapid QR code tag lookup for mobile scanning |

### Maintenance & Work Orders
| Method | Route | Permission | Description |
|---|---|---|---|
| `GET` | `/maintenance` | Authenticated | Fetch Kanban board work orders grouped by stage |
| `POST`| `/maintenance` | `maintenance_write` | Raise maintenance issue (triggers push if High priority) |
| `PATCH`| `/maintenance/{id}` | `maintenance_write` | Transition ticket (In Progress, Resolved, Rejected) |
| `DELETE`| `/maintenance/{id}` | `maintenance_write` | Delete work order (restricted to creator or manager) |
| `GET` | `/uploads/signature`| Authenticated | Issue signed Cloudinary direct upload token |
| `POST`| `/maintenance/{id}/photos` | `maintenance_write` | Attach Cloudinary evidence photo |
| `DELETE`| `/maintenance/{id}/photos/{public_id}` | `maintenance_write` | Remove evidence photo |

*Note: Resolved maintenance items are automatically deleted after 30 days.*

### Bookings & Facility Reservations
| Method | Route | Permission | Description |
|---|---|---|---|
| `GET` | `/bookings` | Authenticated | List all active and upcoming calendar reservations |
| `POST`| `/bookings` | `booking` | Reserve a lab, hall, bus, or projector |
| `DELETE`| `/bookings/{id}` | `booking` | Cancel an existing reservation |

### Audits & No-Dues Clearance
| Method | Route | Permission | Description |
|---|---|---|---|
| `GET` | `/audits` | `audit` | List historical and active audit cycles |
| `POST`| `/audits` | `audit` | Initiate a new departmental physical audit run |
| `PATCH`| `/audits/{audit_id}/items/{asset_id}` | `audit` | Mark item status (`Verified`, `Missing`, `Damaged`) |
| `POST`| `/audits/{audit_id}/items/{asset_id}/photos` | `audit` | Attach physical verification photo |
| `POST`| `/audits/{audit_id}/close` | `audit` | Close audit run and compile final reconciliation |
| `GET` | `/audits/{audit_id}/pdf` | `audit` | Stream generated audit report PDF |
| `GET` | `/nodues` | `nodues` | List all student clearance statuses (Admin only) |
| `PATCH`| `/nodues/{student_id}/{dept}` | `nodues` | Update department clearance status |

### Reports, Digest & Push Notifications
| Method | Route | Permission | Description |
|---|---|---|---|
| `GET` | `/reports` | `reports` | Operational asset utilization summary |
| `GET` | `/reports/accreditation` | `reports` | NAAC/NBA accreditation data indicators |
| `GET` | `/reports/accreditation/download` | `reports` | Download signed NAAC/NBA report (PDF or CSV) |
| `GET` | `/digest/weekly` | `reports` | Executive Monday digest (briefing + print view) |
| `GET` | `/notifications` | Authenticated | Fetch user notification feed |
| `POST`| `/notifications/mark-all-read` | Authenticated | Mark all notifications read |
| `GET` | `/push/public-key` | Authenticated | Retrieve server VAPID public key |
| `POST`| `/push/subscribe` | Authenticated | Store browser push notification subscription |
| `POST`| `/push/unsubscribe` | Authenticated | Remove push notification subscription |

### Administration & Configuration
| Method | Route | Permission | Description |
|---|---|---|---|
| `GET`/`POST` | `/admin/departments` | `admin` | List or create academic/operational departments |
| `GET`/`POST` | `/admin/categories` | `admin` | List or create asset classification categories |
| `GET` | `/admin/users` | `admin` | List all registered campus accounts |
| `PATCH` | `/admin/users/{id}/role` | `admin` | Promote or modify user role and status |
| `GET` | `/admin/role-preview/{role}` | `admin` | Test UI capability permissions for a role |
| `GET`/`PUT` | `/admin/branding` | `admin` | Update institution name, logo, accent color, footer |
| `GET`/`POST` | `/admin/delegations` | `admin` | List or create scheduled Admin delegation windows |
| `DELETE` | `/admin/delegations/{id}` | `admin` | Revoke an administrative delegation slot |
| `POST` | `/admin/imports/{kind}` | `admin` | Bulk import assets or users from CSV files |
| `GET`/`POST` | `/admin/templates` | `admin` | List or configure custom report templates |
| `GET`/`PATCH`/`DELETE` | `/admin/templates/{id}` | `admin` | Manage specific custom report template |
| `POST` | `/admin/seed` | `admin` | Refresh or repopulate the 260-asset demo dataset |

---

## 🗄 Data Model & MongoDB Collections

| Collection | Description & Key Document Fields |
|---|---|
| `users` | `user_id`, `name`, `email`, `role`, `department`, `status`, `password_hash`, `picture`, `created_at` |
| `user_sessions` | `session_token`, `user_id`, `created_at`, `expires_at` |
| `assets` | `asset_id`, `tag`, `name`, `category`, `department`, `location`, `status`, `serial`, `bookable`, `holder`, `purchase_cost`, `warranty_end` |
| `maintenance` | `request_id`, `asset_id`, `description`, `priority`, `status`, `raised_by`, `photos[]`, `created_at`, `resolved_at` |
| `bookings` | `booking_id`, `resource_id`, `resource_name`, `user_id`, `date`, `start_time`, `end_time`, `purpose`, `status` |
| `audits` | `audit_id`, `department`, `period`, `status`, `auditors[]`, `items[{asset_id, verification, note, photos[]}]` |
| `nodues` | `student_id`, `student_name`, `roll_number`, `overall_status`, `department_statuses[{department, status, note}]` |
| `activity` | `event_id`, `actor_id`, `actor_name`, `action`, `entity_type`, `entity_id`, `before`, `after`, `timestamp` |
| `departments` | `department_id`, `name`, `type`, `head`, `status` |
| `categories` | `category_id`, `name`, `example_items`, `warranty_tracked`, `amc_tracked` |
| `branding` | `institution_name`, `tagline`, `accreditation_body`, `footer_text`, `accent_color`, `logo_url` |
| `delegations` | `delegation_id`, `admin_id`, `deputy_id`, `deputy_email`, `start_at`, `end_at`, `status` |
| `push_subs` | `user_id`, `endpoint`, `keys{p256dh, auth}`, `created_at` |
| `report_templates` | `template_id`, `name`, `description`, `data_source`, `columns[]`, `filters{}`, `access_roles[]` |

---

## 📦 Demo Dataset & Seeding

The backend ships with an enterprise-scale seed generator in `seed_data.py`:
- Populates **260 realistic assets** across 15 campus departments and 10 categories.
- Populates **50 maintenance tickets**, **45 bookings**, **12 audits**, **35 no-dues records**, and **300 activity logs**.
- Populates **28 demo users** across all permission tiers.

```bash
# Populate or reset seed data
python seed_data.py

# Seed while preserving existing records
python seed_data.py --keep
```

---

## 💻 Local Setup & Development

```bash
# 1. Activate Python virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
source venv/bin/activate # Linux/macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Start local development server with hot-reload
uvicorn server:app --reload --host 0.0.0.0 --port 8001
```

---

## 🧪 Testing & Quality Assurance

```bash
# Run complete test suite
pytest

# Run tests with verbose output
pytest -v

# Run with test coverage
pytest --cov=server tests/
```

---

## 🚀 Deployment

- **Containerized**: Deploy via standard Dockerfile with Python 3.11-slim.
- **Supervisor**: Manage via `/etc/supervisor/conf.d/backend.conf` on port 8001.
- **Ingress**: Reverse proxy route `/api` to port 8001 with preserved cookies.

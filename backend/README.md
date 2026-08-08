# AssetFlow Campus — Backend

A **FastAPI** service (Python 3.11) backed by **MongoDB** (via the async **Motor**
driver). It exposes a JSON API under the `/api` prefix, enforces cookie-based
authentication and server-side role-based access control (RBAC), and integrates
Cloudinary (uploads), ReportLab (PDF), and Web Push (VAPID).

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

## 6. Integrations

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

## 7. Environment & Run

`backend/.env`:
```
MONGO_URL=<atlas connection string>
DB_NAME=assetflow_campus
CORS_ORIGINS=*
CLOUDINARY_CLOUD_NAME= / CLOUDINARY_API_KEY= / CLOUDINARY_API_SECRET=
VAPID_PUBLIC_KEY= / VAPID_PRIVATE_KEY= / VAPID_SUBJECT=
```

```bash
pip install -r requirements.txt
sudo supervisorctl restart backend      # runs uvicorn on 0.0.0.0:8001
tail -n 50 /var/log/supervisor/backend.err.log
```

- **Seeding:** an idempotent `seed()` runs on startup — creates demo admin/manager,
  sample assets, departments, categories and no-dues if missing.
- **Key libraries:** `fastapi`, `motor`, `pydantic`, `bcrypt`, `cloudinary`,
  `reportlab`, `pywebpush`, `requests`, `python-dotenv` (see `requirements.txt`).

# AssetFlow Campus

**Every asset. Accountable. From one calm workspace.**

AssetFlow Campus is a full-stack campus asset-management platform for colleges and
universities. It tracks physical assets across their whole lifecycle — registration,
allocation (check-out / check-in), bookings, maintenance, audits, student no-dues
clearance and accreditation (NAAC/NBA) reporting — behind a strict, server-enforced
role-based access control (RBAC) system.

The UI is fully responsive (mobile → desktop), touch-friendly, and includes a
PWA-style mobile QR check-in flow, a Trello-style drag-and-drop maintenance board,
browser push notifications, Cloudinary photo uploads, and signed PDF/CSV report
exports.

---

## 1. Tech Stack

| Layer            | Technology |
|------------------|------------|
| **Frontend**     | React 19, React Router 7, CRACO (Create React App), Tailwind CSS, shadcn/ui (Radix primitives), Framer Motion, Recharts, `@hello-pangea/dnd`, `html5-qrcode` + `qrcode.react`, Sonner, next-themes |
| **Backend**      | FastAPI (Python 3.11), Motor (async MongoDB driver), Pydantic v2 |
| **Database**     | MongoDB (Atlas), UUID primary keys (no ObjectIds exposed) |
| **Auth**         | Cookie sessions (bcrypt passwords) + Emergent-managed Google OAuth |
| **File storage** | Cloudinary (signed direct uploads) |
| **PDF / reports**| ReportLab (server-side PDF), CSV export |
| **Push**         | Web Push via `pywebpush` (VAPID) |
| **Process mgmt** | Supervisor (frontend :3000, backend :8001), Kubernetes ingress routes `/api` → backend |

---

## 2. Repository Layout

```
/app
├── backend/            # FastAPI service (see backend/README.md)
│   ├── server.py       # Single-file API: routes, models, RBAC, integrations, seed
│   ├── requirements.txt
│   └── README.md
├── frontend/           # React SPA (see frontend/README.md)
│   ├── src/App.js      # All pages, routing, shell, API client
│   ├── src/components/ui   # shadcn/ui component library
│   └── README.md
├── memory/             # PRD, wireframes, test credentials
├── tests/              # Backend + Playwright UI verification scripts
└── test_result.md      # Testing protocol & history
```

---

## 3. Core Features

- **Dashboard** — KPIs (total / available / in-maintenance assets, utilisation %) + live activity feed.
- **Inventory** — searchable/filterable asset register, asset detail, check-out / check-in, bookable flag.
- **Bookings** — reserve bookable assets for a time window.
- **Maintenance** — Trello-style Kanban board (Open → In progress → Resolved) with drag-and-drop, an **Advance** dropdown (Move to next stage / Move to Resolved / Reject / Delete), Cloudinary damage-photo attachments, and **auto-expiry: resolved items are permanently deleted after 30 days**.
- **Audits** — create audit runs, mark item conditions, attach evidence photos, close audit → PDF.
- **No-Dues** — per-department student clearance tracking (Library / Hostel / Sports …).
- **Reports** — operational report + **NAAC/NBA accreditation report** exportable as signed **PDF or CSV** with an admin-editable institution cover sheet.
- **Weekly Digest** (`/digest`, admin) — Monday KPIs, open work orders, pending approvals, upcoming bookings, open audits; Print + PDF export.
- **Scan** (`/scan`) — mobile-friendly QR scan-to-check-out/in flow for custodians (PWA meta tags, 44px touch targets).
- **Admin console** — departments, categories, users & role changes, delegation slots, CSV bulk import, branding/cover-sheet, role-preview playground.
- **Notifications Center** — real feed (maintenance escalations, reminders) + browser push for high-priority work orders.

---

## 4. Roles & Access Control (RBAC)

Roles: **Admin, Asset Manager, HOD, Employee, Student**. Permissions are enforced
**server-side** on every protected route (not just hidden in the UI).

| Permission     | Admin | Asset Manager | HOD | Employee | Student |
|----------------|:-----:|:-------------:|:---:|:--------:|:-------:|
| admin          | ✅ | — | — | — | — |
| asset_write    | ✅ | ✅ | ✅ | — | — |
| maintenance_write | ✅ | ✅ | ✅ | ✅ | ✅ |
| booking        | ✅ | ✅ | ✅ | ✅ | ✅ |
| audit          | ✅ | ✅ | — | — | — |
| nodues         | ✅ | — | — | — | — |
| reports        | ✅ | ✅ | ✅ | ✅ | — |

- New signups default to **Student / Pending**; only an Admin can promote roles (no self-assigned admin).
- **Delegation slots:** an Admin can temporarily elevate a deputy to Admin for a fixed time window; the elevation is applied automatically at request time and expires when the window closes.

---

## 5. Local / Platform Setup

Services are managed by **Supervisor** — never start servers manually.

```bash
# Install deps
cd /app/backend && pip install -r requirements.txt
cd /app/frontend && yarn install

# Restart services
sudo supervisorctl restart backend frontend
sudo supervisorctl status
```

### Environment variables

**`backend/.env`**
```
MONGO_URL=<mongodb atlas connection string>
DB_NAME=assetflow_campus
CORS_ORIGINS=*
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
VAPID_PRIVATE_KEY=...
VAPID_PUBLIC_KEY=...
VAPID_SUBJECT=mailto:admin@assetflow.edu
```

**`frontend/.env`**
```
REACT_APP_BACKEND_URL=<external backend base url>
```
> Never hardcode URLs/ports. Frontend calls the backend via `REACT_APP_BACKEND_URL`;
> all backend routes are prefixed with `/api` for Kubernetes ingress.

### Demo accounts

| Role          | Email               | Password   |
|---------------|---------------------|------------|
| Admin         | admin@assetflow.edu | Admin123!  |
| Asset Manager | demo@assetflow.edu  | Campus123! |

Seeded idempotently on backend startup.

---

## 6. Documentation

- **[frontend/README.md](frontend/README.md)** — pages, routes, components, state, API client.
- **[backend/README.md](backend/README.md)** — endpoints, models, collections, RBAC internals, integrations.

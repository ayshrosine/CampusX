# AssetFlow Campus — Frontend

A responsive React single-page application (SPA) that adapts fluidly from mobile
phones to desktop. It talks to the FastAPI backend over a cookie-authenticated
JSON API and enforces the same roles the backend enforces (UI-level gating on top
of server-level RBAC).

---

## 1. Tech Stack

| Concern            | Library / Tool |
|--------------------|----------------|
| Framework          | **React 19** |
| Build / tooling    | **Create React App + CRACO** (`craco start/build`) |
| Routing            | **react-router-dom 7** |
| Styling            | **Tailwind CSS** + `tailwind-merge`, `tailwindcss-animate`, `clsx`, `class-variance-authority` |
| UI components      | **shadcn/ui** (Radix UI primitives) in `src/components/ui` |
| Animation          | **Framer Motion** |
| Charts             | **Recharts** (dashboard/digest KPIs) |
| Drag & drop        | **@hello-pangea/dnd** (Trello-style maintenance Kanban) |
| QR                 | **html5-qrcode** (scanner) + **qrcode.react** (asset QR codes) |
| Notifications/UI   | **Sonner** (toasts), Web Push subscription via service worker |
| Theming            | **next-themes** (light/dark) |
| HTTP / data        | **axios** (with `withCredentials`), SWR / React Query available |
| Forms/validation   | **react-hook-form** + **zod** |
| Icons              | **lucide-react** |

> **Responsive design:** layouts use fluid grids, `%` / viewport units and Tailwind
> breakpoints (`sm md lg xl`) to rearrange, shrink and hide components per screen
> size. Touch targets are ≥44px; the `/scan` page ships PWA meta tags so custodians
> can add it to their home screen.

---

## 2. Project Structure

```
frontend/
├── craco.config.js        # CRA override (aliases, tailwind)
├── tailwind.config.js
├── public/                # index.html (PWA meta), service worker, icons
└── src/
    ├── index.js           # React root, providers
    ├── App.js             # ⭐ ALL pages, routing, Shell layout, API client
    ├── App.css / index.css
    ├── components/ui/      # shadcn/ui library (button, dialog, table, tabs, …)
    ├── hooks/use-toast.js
    ├── lib/utils.js        # cn() classnames helper
    └── constants/testIds/  # stable data-testid selectors for tests
```

> The app is intentionally consolidated in **`src/App.js`**: each page is a function
> component defined in that file, wrapped by a shared `Shell` (sidebar + top bar +
> notification bell) and guarded by `ProtectedApp`.

---

## 3. Routing & Pages

All authenticated routes render inside `Shell`. Unauthenticated users are sent to
`/login`.

| Route                     | Component      | Purpose |
|---------------------------|----------------|---------|
| `/login`                  | `Login`        | Email/password + "Continue with Google" (Emergent-managed OAuth) |
| `/dashboard`              | `Dashboard`    | KPI cards + live activity feed |
| `/inventory`              | `Inventory`    | Asset register: search, status/category filters |
| `/inventory/:asset_id`    | `AssetDetail`  | Asset details, QR code, check-out / check-in |
| `/bookings`               | `Bookings`     | Reserve bookable assets |
| `/maintenance`            | `Maintenance`  | Kanban board (drag & drop) + Advance dropdown + photos |
| `/audits`                 | `Audits`       | Audit runs, item conditions, evidence photos, close→PDF |
| `/nodues`                 | `NoDues`       | Student clearance by department |
| `/reports`                | `Reports`      | Operational + NAAC/NBA accreditation export (PDF/CSV) |
| `/activity`               | `ActivityPage` | Full audit log |
| `/digest`                 | `DigestPage`   | Admin weekly digest (Print / PDF) |
| `/admin`                  | `Admin`        | Departments, categories, users/roles, delegations, imports, branding, role-preview |
| `/scan`                   | `ScanPage`     | Mobile QR scan → check-out / check-in |
| `*`                       | `Dashboard`    | Fallback |

### How the pages connect

```
index.js
  └── App (theme + toaster providers)
        └── ProtectedApp        # calls GET /api/auth/me on load
              ├── (no session) → <Login/>
              └── (session)    → <Shell user=…>
                                    ├── Sidebar nav (role-filtered links)
                                    ├── NotificationBell (feed + push)
                                    └── <Routes> … page components …
```

- **`ProtectedApp`** bootstraps auth: it requests `GET /api/auth/me`. On success it
  stores the `user` (name, role, department) and renders the shell; on 401 it shows `Login`.
- **`Shell`** receives `user` and shows only the nav links the role is allowed to
  see, plus the logout action and the notification bell.
- **Role gating** in the UI mirrors backend `ROLE_PERMISSIONS`; the backend remains
  the source of truth (any blocked API call returns 403).

---

## 4. API Client & Auth Flow

- Base URL: **`process.env.REACT_APP_BACKEND_URL` + `/api`** (never hardcoded).
- All requests use **`withCredentials: true`** so the httpOnly `session_token`
  cookie is sent automatically.
- **Email/password:** `POST /api/auth/login` → sets cookie → app reloads user.
- **Google:** redirects to Emergent-managed auth, returns with a session id which is
  exchanged via `POST /api/auth/session` (sets the same cookie). New Google users
  start as Student/Pending.
- **Logout:** `POST /api/auth/logout` clears the cookie.

---

## 5. Feature Notes

- **Maintenance Kanban** — columns are drag-and-drop (`@hello-pangea/dnd`). Each card
  has an **Advance** dropdown: *Move to next stage / Move to Resolved / Reject / Delete*.
  Resolved cards are auto-purged 30 days after resolution (enforced backend-side).
  Photos upload directly to Cloudinary using a signature fetched from the backend.
- **Scan** — `html5-qrcode` reads an asset tag, looks it up via
  `GET /api/assets/by-tag/{tag}`, then checks the asset out/in. Optimised for
  one-handed mobile use.
- **Reports / Digest** — call the backend PDF/CSV endpoints and stream the file to the
  browser for download or print.
- **Push notifications** — the app fetches the VAPID public key, subscribes via the
  service worker, and posts the subscription to `POST /api/push/subscribe`.

---

## 6. Run / Build

```bash
yarn install
# Dev server is managed by supervisor on port 3000:
sudo supervisorctl restart frontend
# Production build:
yarn build
```

Lint: `eslint` via CRACO config. Do not change `.env` URLs/ports.

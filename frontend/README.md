# AssetFlow Campus — Frontend Client

A responsive, high-fidelity **React 19** single-page application (SPA) built with **React Router 7**, **Tailwind CSS**, and **shadcn/ui** (Radix UI primitives). It adapts fluidly across mobile phones, tablets, and desktop workstations, connects to the FastAPI backend over a cookie-authenticated JSON API, and provides a mobile PWA QR-code scanning workflow.

---

## 📋 Table of Contents

- [Architecture & Design System](#architecture--design-system)
- [Archify Architecture Specifications](#archify-architecture-specifications)
- [Directory Layout](#directory-layout)
- [Routing & Application Pages](#routing--application-pages)
- [API Client & Authentication](#api-client--authentication)
- [Key Features & Interactivity](#key-features--interactivity)
- [Component Architecture & UI Primitives](#component-architecture--ui-primitives)
- [Styling, Theming & Responsiveness](#styling-theming--responsiveness)
- [PWA & Mobile QR Workflow](#pwa--mobile-qr-workflow)
- [Local Development Setup](#local-development-setup)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Build & Deployment](#build--deployment)

---

## 🏛 Architecture & Design System

```
Browser / Mobile PWA Viewport
  └── index.js (Theme Provider + Sonner Toaster)
        └── App.js
              ├── /login (Login Form with Email/Password & Google Sign-In)
              └── ProtectedApp (AuthGate wrapping all authenticated views)
                    └── Shell (Responsive Navigation + Dynamic Top Bar + Notifications)
                          ├── Sidebar Navigation (Filtered by User RBAC Role)
                          ├── Top Bar (Theme Toggle, Search, Notification Bell, User Avatar)
                          └── <Routes> (12 Authenticated Pages + Fallback)
```

- **Consolidated Component Pattern**: The core application logic, Shell layout, and all 13 view components are neatly structured in `src/App.js` with shared design tokens and atomic utility styling.
- **Wope & Geist Inspired Aesthetics**: Features clean borders, subtle hover interactions, Geist monospace data accents, and high-contrast dark/light mode switching.
- **Client-Side RBAC Mirroring**: Mirrors the backend `ROLE_PERMISSIONS` dictionary to display only authorized navigation links and controls, while relying on the backend as the ultimate authority.

---

## 📐 Archify Architecture Specifications

The frontend interacts with the system through 5 architecture models defined in `docs/architecture/`:

1. **[System Architecture](file:///d:/projects/CampusX/docs/architecture/system-architecture.html)**: Shows how React SPA and Mobile PWA connect to the FastAPI Ingress.
2. **[Maintenance Workflow](file:///d:/projects/CampusX/docs/architecture/maintenance-workflow.html)**: Shows how users report issues and track Kanban transitions.
3. **[QR Checkout Sequence](file:///d:/projects/CampusX/docs/architecture/qr-checkout.html)**: Traces the `/scan` camera interaction and checkout API handshakes.
4. **[Asset Dataflow](file:///d:/projects/CampusX/docs/architecture/asset-dataflow.html)**: Maps UI state mutations into MongoDB Atlas and the Activity Log.
5. **[Asset Lifecycle](file:///d:/projects/CampusX/docs/architecture/asset-lifecycle.html)**: Illustrates the visual badge states for physical assets.

---

## 📁 Directory Layout

```
frontend/
├── public/                            # Static assets, PWA manifest, and service worker
│   ├── index.html                     # HTML5 template with PWA viewport and meta tags
│   └── sw.js                          # Service worker for Web Push notification handling
├── src/
│   ├── App.js                         # ⭐ Master application: Shell, Router, API client, all 13 pages
│   ├── index.js                       # Application entry point, ThemeProvider, and Toaster
│   ├── App.css                        # Platform utility CSS, Geist font tokens, and layout styles
│   ├── index.css                      # Tailwind base and theme variables
│   ├── components/
│   │   ├── OrbitTrails.jsx            # Animated canvas hero graphic
│   │   └── ui/                        # 40+ shadcn/ui components (Button, Dialog, Tabs, Table, etc.)
│   ├── hooks/
│   │   └── use-toast.js               # Toast notification hook
│   ├── lib/
│   │   └── utils.js                   # Classname merge utility (clsx + twMerge)
│   └── constants/
│       └── testIds/                   # Stable data-testid selectors for automated tests
│           ├── auth.js
│           ├── home.js
│           └── index.js
├── plugins/
│   └── health-check/                  # Build-time and runtime health monitoring plugins
├── craco.config.js                    # CRA configuration override (Tailwind + aliases)
├── tailwind.config.js                 # Tailwind CSS configuration and color tokens
├── postcss.config.js                  # PostCSS plugins
├── components.json                    # shadcn/ui CLI configuration
├── jsconfig.json                      # Path aliases mapping (@/* -> src/*)
├── package.json                       # Dependencies and build scripts
└── README.md                          # Frontend documentation (this file)
```

---

## 🗺 Routing & Application Pages

All authenticated routes are rendered within the `Shell` layout component.

| Route | Component | Required Role / Permission | Purpose |
|---|---|---|---|
| `/login` | `Login` | Public | Email/password sign-in and Google OAuth login |
| `/dashboard` | `Dashboard` | Authenticated | Executive KPIs, asset health, and live activity stream |
| `/inventory` | `Inventory` | Authenticated | Searchable asset catalog with category and status filters |
| `/inventory/:asset_id` | `AssetDetail` | Authenticated | Hardware specs, QR code display, and check-out/in modals |
| `/bookings` | `Bookings` | `booking` | Calendar scheduler for labs, halls, and equipment |
| `/maintenance` | `Maintenance` | `maintenance_write` | Drag-and-drop Kanban board with Cloudinary photo uploads |
| `/audits` | `Audits` | `audit` | Departmental audit runs, reconciliation, and PDF export |
| `/nodues` | `NoDues` | `nodues` | Student clearance tracking across campus departments |
| `/reports` | `Reports` | `reports` | Operational and NAAC/NBA accreditation report downloads |
| `/activity` | `ActivityPage` | Authenticated | Complete audit log with filters for alerts and approvals |
| `/digest` | `DigestPage` | `admin` | Monday executive briefing with print-friendly layout |
| `/admin` | `Admin` | `admin` | Departments, categories, roles, delegations, seed dataset |
| `/scan` | `ScanPage` | Authenticated | Mobile camera barcode/QR scanner for rapid field checkout |
| `*` | `Dashboard` | Authenticated | Fallback route redirecting to Dashboard |

---

## 🌐 API Client & Authentication

The frontend communicates with the backend via the unified `api(path, options)` helper in `src/App.js`:

```javascript
const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

const api = async (path, options = {}) => {
  const res = await fetch(`${API}${path}`, {
    credentials: "include", // Ensures httpOnly session_token cookie is transmitted
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  // Handles errors and extracts FastAPI 422 validation detail messages
};
```

- **Cookie-Based Sessions**: Requests automatically send the secure `session_token` cookie.
- **Error Formatting**: Formats FastAPI 422 schema errors and detail strings cleanly into Sonner toast alerts.
- **Google OAuth Flow**: The login page renders Google Sign-In buttons, which submit the Google ID token to `POST /api/auth/session` to obtain a session cookie.

---

## ✨ Key Features & Interactivity

- **Drag-and-Drop Maintenance Kanban**: Built using `@hello-pangea/dnd`. Cards drag between *Open*, *In progress*, and *Resolved*. Each card includes an **Advance** dropdown (*Next Stage*, *Mark Resolved*, *Reject*, *Delete*).
- **Direct Cloudinary Image Uploads**: Uploads bypass server memory bottlenecks. The client fetches a short-lived signature from `GET /api/uploads/signature` and uploads directly to Cloudinary via HTTPS.
- **Interactive SVG QR Generation**: Every asset details page renders an SVG QR code via `qrcode.react`, allowing immediate label printing.
- **Web Push Notifications**: Uses the browser `PushManager` and `public/sw.js` to subscribe devices to VAPID push alerts for high-priority incidents.
- **Dark & Light Mode**: Controlled seamlessly via CSS variables (`--bg`, `--surface`, `--ink`, `--mute`) and toggleable from the navigation shell.

---

## 🧩 Component Architecture & UI Primitives

The project includes 40+ modular shadcn/ui components located in `src/components/ui/`:

- **Layout & Structure**: `card.jsx`, `dialog.jsx`, `sheet.jsx`, `drawer.jsx`, `tabs.jsx`, `separator.jsx`, `scroll-area.jsx`
- **Actions & Forms**: `button.jsx`, `input.jsx`, `textarea.jsx`, `select.jsx`, `checkbox.jsx`, `dropdown-menu.jsx`, `form.jsx`
- **Feedback & Visuals**: `badge.jsx`, `avatar.jsx`, `progress.jsx`, `skeleton.jsx`, `sonner.jsx`, `tooltip.jsx`
- **Visual Motion**: `OrbitTrails.jsx` — interactive orbiting canvas graphic on the landing and login views.

---

## 📱 PWA & Mobile QR Workflow

The `/scan` route is specifically engineered for campus field custodians:
- **Camera-Based Scanning**: Utilizes `html5-qrcode` to decode physical asset tags in real time.
- **Touch-First UI**: All primary buttons and action controls adhere to standard mobile touch targets (≥44px).
- **PWA Meta Headers**: Includes `theme-color`, `mobile-web-app-capable`, and viewport settings in `public/index.html` allowing users to save AssetFlow directly to their home screens.

---

## 💻 Local Development Setup

```bash
# 1. Install dependencies
yarn install
# or: npm install

# 2. Configure environment
cp .env.example .env
# Ensure REACT_APP_BACKEND_URL=http://localhost:8001

# 3. Start development server
yarn start
# or: npm start
```
*The React application will be accessible at `http://localhost:3000`.*

---

## 🧪 Testing & Quality Assurance

```bash
# Run Jest / React Testing Library suites
yarn test --watchAll=false

# Run code linter
yarn lint
```

The application provides stable `data-testid` attributes defined in `src/constants/testIds/` (e.g. `data-testid="login-email"`, `data-testid="trigger-seed-button"`), enabling resilient end-to-end and integration testing.

---

## 🚀 Build & Deployment

```bash
# Create optimized production bundle
yarn build
# or: npm run build
```

The output in `build/` is static and can be deployed directly to Vercel, Netlify, AWS S3/CloudFront, or served via Nginx.

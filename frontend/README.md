# AssetFlow Campus — Frontend

A responsive React single-page application (SPA) that adapts fluidly from mobile
phones to desktop. It talks to the FastAPI backend over a cookie-authenticated
JSON API and enforces the same roles the backend enforces (UI-level gating on top
of server-level RBAC).

---

## 📋 Table of Contents

- [Tech Stack](#tech-stack)
- [Local Development Setup](#local-development-setup)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Routing & Pages](#routing--pages)
- [API Client & Auth Flow](#api-client--auth-flow)
- [Feature Notes](#feature-notes)
- [Component Library](#component-library)
- [Styling & Theming](#styling--theming)
- [Testing](#testing)
- [Build & Deployment](#build--deployment)
- [Troubleshooting](#troubleshooting)

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

## 2. Local Development Setup

### Prerequisites

- **Node.js** (v18 or higher) - [Download here](https://nodejs.org/)
- **Yarn** (recommended) or npm - `npm install -g yarn`
- **Git** - [Download here](https://git-scm.com/downloads)

### Step-by-Step Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install Node.js dependencies:**
   ```bash
   yarn install
   # or with npm:
   npm install
   ```

3. **Configure environment variables:**
   Create a `.env` file by copying the example file:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` with your backend URL if needed (see [Environment Variables](#environment-variables) section)

4. **Start the development server:**
   ```bash
   yarn start
   # or with npm:
   npm start
   ```

5. **Access the application:**
   Open your browser and navigate to `http://localhost:3000`

The development server will automatically reload when you make changes to the code.

### Development Tools

**Code Formatting and Linting:**
```bash
# Lint code
yarn lint
# or with npm:
npm run lint

# Fix linting issues
yarn lint --fix
```

**Running Tests:**
```bash
yarn test
# or with npm:
npm test
```

---

## 3. Environment Variables

Create a `.env` file by copying the example file:
```bash
cp .env.example .env
```
Then edit `.env` with your backend URL if needed. The example file contains the required variables with placeholder values.

**Required Variables:**
- `REACT_APP_BACKEND_URL` - Backend API URL (e.g., http://localhost:8001)
- `REACT_APP_GOOGLE_CLIENT_ID` - Google OAuth client ID (optional)

**Important Notes:**
- Never commit the `.env` file to version control
- The backend URL must include the protocol (http:// or https://)
- In production, use HTTPS for secure connections
- The frontend expects the backend to be accessible at the configured URL

---

## 4. Project Structure

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

## 5. Routing & Pages

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

## 6. API Client & Auth Flow

- Base URL: **`process.env.REACT_APP_BACKEND_URL` + `/api`** (never hardcoded).
- All requests use **`withCredentials: true`** so the httpOnly `session_token`
  cookie is sent automatically.
- **Email/password:** `POST /api/auth/login` → sets cookie → app reloads user.
- **Google:** redirects to Emergent-managed auth, returns with a session id which is
  exchanged via `POST /api/auth/session` (sets the same cookie). New Google users
  start as Student/Pending.
- **Logout:** `POST /api/auth/logout` clears the cookie.

---

## 7. Feature Notes

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

## 8. Component Library

The application uses **shadcn/ui** components built on Radix UI primitives. These are located in `src/components/ui/`.

**Available Components:**
- Button
- Dialog
- Table
- Tabs
- Form
- Input
- Select
- Dropdown Menu
- Avatar
- Card
- Alert
- Toast (via Sonner)
- And many more...

**Usage Example:**
```jsx
import { Button } from './components/ui/button'

function MyComponent() {
  return <Button>Click me</Button>
}
```

All components follow the shadcn/ui conventions and are fully customizable via Tailwind CSS classes.

---

## 9. Styling & Theming

### Tailwind CSS

The application uses Tailwind CSS for styling with a custom configuration in `tailwind.config.js`.

**Key Features:**
- Responsive design using mobile-first approach
- Dark mode support via `next-themes`
- Custom color palette and design tokens
- Animation utilities via `tailwindcss-animate`

### Theme Configuration

**Light/Dark Mode:**
- Theme switching is handled by `next-themes`
- Theme preference is persisted in localStorage
- System preference is respected by default

**Custom Colors:**
- Primary colors are configurable via the `branding` collection in the backend
- Accent colors can be customized through the Admin console

### Responsive Breakpoints

- `sm`: 640px and up
- `md`: 768px and up
- `lg`: 1024px and up
- `xl`: 1280px and up

---

## 10. Testing

### Running Tests

```bash
# Run tests in watch mode
yarn test
# or with npm:
npm test
```

### Test Structure

- **Component tests**: Test individual React components
- **Integration tests**: Test page flows and user interactions
- **E2E tests**: End-to-end testing with Playwright (if configured)

### Test IDs

The application uses stable `data-testid` selectors for testing, located in `src/constants/testIds/`. These provide reliable selectors for automated testing.

### Testing Best Practices

- Use `data-testid` attributes for selecting elements in tests
- Test user behavior rather than implementation details
- Mock API calls for unit and integration tests
- Use React Testing Library for component testing

---

## 11. Build & Deployment

### Development Build

```bash
# Start development server
yarn start
# or with npm:
npm start
```

The development server runs on `http://localhost:3000` with hot module replacement.

### Production Build

```bash
# Create optimized production build
yarn build
# or with npm:
npm run build
```

The production build will be created in the `build/` directory.

### Build Configuration

- **CRACO** (Create React App Configuration Override) is used for custom build configuration
- Configuration is defined in `craco.config.js`
- Tailwind CSS is processed during the build
- Environment variables are embedded at build time

### Deployment

**Static Hosting:**
The `build/` directory can be deployed to any static hosting service:
- Netlify
- Vercel
- AWS S3 + CloudFront
- GitHub Pages

**Docker Deployment:**
Create a `Dockerfile`:

```dockerfile
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN yarn install
COPY . .
RUN yarn build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Environment-Specific Builds:**
- Create different `.env` files for each environment
- Build with the appropriate environment variables
- Deploy the build output to the corresponding environment

---

## 12. Troubleshooting

### Common Issues

**Development server won't start:**
- Ensure Node.js version is 18 or higher
- Delete `node_modules` and `package-lock.json`, then reinstall
- Check that port 3000 is not already in use
- Verify `.env` file exists and is correctly configured

**Build fails:**
- Check for TypeScript errors in components
- Verify all imports are correct
- Ensure Tailwind CSS configuration is valid
- Check that environment variables are set

**Styles not loading:**
- Verify Tailwind CSS is properly configured
- Check that `craco.config.js` is correctly set up
- Ensure PostCSS configuration is valid
- Clear browser cache and restart dev server

**API calls failing:**
- Verify `REACT_APP_BACKEND_URL` is correct in `.env`
- Check that backend is running and accessible
- Ensure CORS is configured correctly on the backend
- Check browser console for specific error messages

**Components not rendering:**
- Check for JavaScript errors in browser console
- Verify component imports are correct
- Ensure data is being fetched properly from the API
- Check React DevTools for component state issues

### Debug Mode

Enable additional debugging by setting environment variables:

```env
REACT_APP_DEBUG=true
```

### Performance Optimization

- Use React.memo for expensive components
- Implement code splitting for large pages
- Optimize images and assets
- Use lazy loading for routes and components
- Enable production build for performance testing

---

## Key Dependencies

The frontend uses the following key libraries (see `package.json` for full list):

- **React 19** - UI library
- **React Router 7** - Client-side routing
- **Tailwind CSS** - Utility-first CSS framework
- **shadcn/ui** - Pre-built UI components
- **Framer Motion** - Animation library
- **Recharts** - Charting library
- **@hello-pangea/dnd** - Drag and drop functionality
- **html5-qrcode** - QR code scanning
- **qrcode.react** - QR code generation
- **axios** - HTTP client
- **react-hook-form** - Form management
- **zod** - Schema validation
- **swr** - Data fetching and caching
- **sonner** - Toast notifications
- **next-themes** - Theme management

---

## PWA Features

The application includes Progressive Web App (PWA) features for mobile users:

- **Service Worker** - Enables offline functionality and background sync
- **Web App Manifest** - Allows installation on mobile devices
- **Responsive Design** - Optimized for mobile touch targets (≥44px)
- **Push Notifications** - Real-time alerts for maintenance and updates
- **Add to Home Screen** - Users can install the app on their devices

The `/scan` page is specifically optimized for mobile PWA usage with large touch targets and simplified interface.

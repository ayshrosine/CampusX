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

## 📋 Table of Contents

- [Tech Stack](#tech-stack)
- [Repository Layout](#repository-layout)
- [Core Features](#core-features)
- [Roles & Access Control (RBAC)](#roles--access-control-rbac)
- [Local Development Setup](#local-development-setup)
- [External Services Configuration](#external-services-configuration)
- [Environment Variables](#environment-variables)
- [Demo Accounts](#demo-accounts)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [Documentation](#documentation)
- [License](#license)

---

## 🛠 Tech Stack

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

## 📁 Repository Layout

```
CampusX/
├── backend/                   # FastAPI backend service
│   ├── server.py             # Single-file API: routes, models, RBAC, integrations, seed
│   ├── requirements.txt      # Python dependencies
│   ├── .env                  # Backend environment variables (not in git)
│   ├── tests/                # Backend test files
│   └── README.md             # Backend-specific documentation
├── frontend/                  # React frontend application
│   ├── src/
│   │   ├── App.js           # Main application with all pages and routing
│   │   ├── components/      # React components
│   │   │   └── ui/          # shadcn/ui component library
│   │   ├── hooks/           # Custom React hooks
│   │   ├── lib/             # Utility functions
│   │   └── constants/       # Constants and test IDs
│   ├── public/              # Static assets, service worker, PWA manifest
│   ├── package.json         # Node.js dependencies
│   ├── .env                 # Frontend environment variables (not in git)
│   └── README.md            # Frontend-specific documentation
├── memory/                   # Project documentation and design materials
│   ├── PRD.md               # Product Requirements Document
│   └── wireframes.html      # UI/UX wireframes
├── tests/                    # Integration and E2E tests
├── .devin/                   # Devin AI configuration
├── .gitignore               # Git ignore rules
├── auth_testing.md          # Authentication testing checklist
├── README.md                # This file
└── zerops.yaml              # Zerops deployment configuration
```

---

## 🌟 Core Features

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

## 👥 Roles & Access Control (RBAC)

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

## 💻 Local Development Setup

### Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js** (v18 or higher) - [Download here](https://nodejs.org/)
- **Python 3.11** - [Download here](https://www.python.org/downloads/)
- **MongoDB** (either local installation or MongoDB Atlas account)
- **Git** - [Download here](https://git-scm.com/downloads)
- **Yarn** (recommended) or npm - `npm install -g yarn`

### Step 1: Clone the Repository

```bash
git clone <your-repository-url>
cd CampusX
```

### Step 2: Backend Setup

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
   Create a `.env` file in the `backend` directory by copying the example file:
   ```bash
   cp backend/.env.example backend/.env
   ```
   Then edit `backend/.env` with your actual credentials.

5. **Start the backend server:**
   ```bash
   uvicorn server:app --reload --host 0.0.0.0 --port 8001
   ```

   The backend will be available at `http://localhost:8001`

### Step 3: Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd ../frontend
   ```

2. **Install Node.js dependencies:**
   ```bash
   yarn install
   # or with npm:
   npm install
   ```

3. **Configure environment variables:**
   Create a `.env` file in the `frontend` directory by copying the example file:
   ```bash
   cp frontend/.env.example frontend/.env
   ```
   Then edit `frontend/.env` with your backend URL if needed.

4. **Start the frontend development server:**
   ```bash
   yarn start
   # or with npm:
   npm start
   ```

   The frontend will be available at `http://localhost:3000`

### Step 4: Verify Setup

1. **Check backend health:**
   ```bash
   curl http://localhost:8001/api/
   ```

2. **Access the application:**
   Open your browser and navigate to `http://localhost:3000`

3. **Login with demo credentials:**
   - Admin: `admin@assetflow.edu` / `Admin123!`
   - Asset Manager: `demo@assetflow.edu` / `Campus123!`

---

## 🔌 External Services Configuration

This project requires several external services to function properly. Below are detailed instructions for setting up each service.

### 1. MongoDB Atlas Setup

MongoDB Atlas is used as the primary database for the application.

**Setup Steps:**

1. **Create a MongoDB Atlas Account:**
   - Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
   - Sign up for a free account

2. **Create a Cluster:**
   - Click "Build a Database"
   - Choose the free tier (M0)
   - Select a region closest to your users
   - Name your cluster (e.g., "AssetFlowCampus")

3. **Configure Network Access:**
   - Go to Network Access → IP Access List
   - Add your IP address or use `0.0.0.0/0` (allows all IPs - not recommended for production)

4. **Configure Database Access:**
   - Go to Database Access
   - Create a new database user with username and password
   - Grant "Read and write to any database" permissions

5. **Get Connection String:**
   - Go to Database → Connect → Connect your application
   - Copy the connection string
   - Replace `<password>` with your database user password

6. **Update Backend .env:**
   ```env
   MONGO_URL=mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority
   DB_NAME=assetflow_campus
   ```

### 2. Cloudinary Setup

Cloudinary is used for image storage and management (maintenance photos, audit evidence, etc.).

**Setup Steps:**

1. **Create a Cloudinary Account:**
   - Go to [Cloudinary](https://cloudinary.com/)
   - Sign up for a free account

2. **Get API Credentials:**
   - Navigate to the Dashboard
   - Copy the following values:
     - Cloud Name
     - API Key
     - API Secret

3. **Configure Upload Settings (Optional):**
   - Go to Settings → Upload
   - Set up upload presets if needed
   - Configure image transformations and optimizations

4. **Update Backend .env:**
   ```env
   CLOUDINARY_CLOUD_NAME=your_cloud_name
   CLOUDINARY_API_KEY=your_api_key
   CLOUDINARY_API_SECRET=your_api_secret
   ```

### 3. Google OAuth Setup

Google OAuth is managed through Emergent for authentication.

**Setup Steps:**

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project

2. **Enable Google+ API:**
   - Go to APIs & Services → Library
   - Search for "Google+ API" and enable it

3. **Configure OAuth Consent Screen:**
   - Go to APIs & Services → OAuth consent screen
   - Configure the consent screen with your app details
   - Add required scopes: `openid`, `email`, `profile`

4. **Create OAuth 2.0 Credentials:**
   - Go to APIs & Services → Credentials
   - Create OAuth 2.0 Client ID
   - Application type: Web application
   - Add authorized redirect URIs (your domain + `/auth/callback`)
   - Copy the Client ID and Client Secret

5. **Configure with Emergent:**
   - The Emergent service manages the OAuth flow
   - Provide the Google Client ID and Client Secret to your Emergent configuration
   - The backend exchanges Emergent session tokens for local sessions

### 4. Web Push (VAPID) Setup

Web Push notifications are used for maintenance alerts and important updates.

**Setup Steps:**

1. **Generate VAPID Keys:**
   ```bash
   # Using Node.js
   npx web-push generate-vapid-keys
   ```

   Or use the online generator: [VAPID Key Generator](https://web-push-codelab.glitch.me/)

2. **Update Backend .env:**
   ```env
   VAPID_PUBLIC_KEY=your_public_key
   VAPID_PRIVATE_KEY=your_private_key
   VAPID_SUBJECT=mailto:admin@yourdomain.com
   ```

3. **Configure Service Worker:**
   - The service worker is already included in the frontend
   - It handles push subscription and notification display

### 5. ReportLab Setup

ReportLab is used for PDF generation (reports, audits, weekly digest).

**Setup Steps:**

1. **Install Dependencies:**
   - Already included in `requirements.txt`
   - ReportLab 5.0.0 is the current version

2. **Configure Fonts (Optional):**
   - Add custom fonts to the backend if needed
   - Default fonts are included with ReportLab

3. **PDF Templates:**
   - PDF templates are defined in the backend code
   - Branding and cover sheets are configurable via the Admin console

---

## 🔐 Environment Variables

### Backend Environment Variables (`backend/.env`)

```env
# Database Configuration
MONGO_URL=mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority
DB_NAME=assetflow_campus

# CORS Configuration
CORS_ORIGINS=*

# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Web Push (VAPID) Configuration
VAPID_PUBLIC_KEY=your_vapid_public_key
VAPID_PRIVATE_KEY=your_vapid_private_key
VAPID_SUBJECT=mailto:admin@yourdomain.com

# Session Configuration (Optional)
SESSION_EXPIRY_DAYS=7
```

### Frontend Environment Variables (`frontend/.env`)

```env
# Backend API URL
REACT_APP_BACKEND_URL=http://localhost:8001

# For production, use your actual backend URL:
# REACT_APP_BACKEND_URL=https://your-backend-domain.com
```

---

## 👤 Demo Accounts

The following demo accounts are automatically seeded when the backend starts:

| Role          | Email               | Password   | Description |
|---------------|---------------------|------------|-------------|
| Admin         | admin@assetflow.edu | Admin123!  | Full system access |
| Asset Manager | demo@assetflow.edu  | Campus123! | Asset management access |

**Notes:**
- These accounts are created idempotently on backend startup
- New signups default to Student/Pending role
- Only Admin users can promote other users to higher roles
- You can create additional users through the Admin console

---

## 🔄 Development Workflow

### Running Both Services

For local development, you'll need both services running:

**Terminal 1 - Backend:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8001
```

**Terminal 2 - Frontend:**
```bash
cd frontend
yarn install
yarn start
```

### Code Style and Linting

**Backend:**
```bash
cd backend
# Format code
black server.py
# Sort imports
isort server.py
# Lint
flake8 server.py
# Type checking
mypy server.py
```

**Frontend:**
```bash
cd frontend
# Lint
yarn lint
# Fix linting issues
yarn lint --fix
```

### Hot Reload

- **Backend:** Uses `--reload` flag with uvicorn for automatic reloading
- **Frontend:** Create React App includes hot module replacement by default

---

## 🧪 Testing

### Backend Tests

```bash
cd backend
pytest
# Run with coverage
pytest --cov=server
# Run specific test file
pytest tests/test_specific.py
```

### Frontend Tests

```bash
cd frontend
yarn test
```

### Integration Tests

```bash
# Run from project root
python backend_test.py
python backend_test_new_features.py
```

See `test_result.md` for detailed testing protocols and history.

---

## 🚀 Deployment

### Production Deployment

The project is configured for deployment using **Zerops** (see `zerops.yaml`).

**Deployment Steps:**

1. **Prepare Environment Variables:**
   - Set all production environment variables in your deployment platform
   - Use production MongoDB Atlas cluster
   - Configure production Cloudinary account
   - Generate production VAPID keys

2. **Build Frontend:**
   ```bash
   cd frontend
   yarn build
   ```

3. **Deploy Backend:**
   - Deploy the FastAPI application
   - Ensure it runs on port 8001
   - Configure ingress to route `/api` to the backend

4. **Deploy Frontend:**
   - Deploy the React build output
   - Configure proper routing for SPA
   - Ensure `REACT_APP_BACKEND_URL` points to production backend

### Supervisor Configuration (Production)

Services are managed by Supervisor in production:

```bash
# Restart services
sudo supervisorctl restart backend frontend
sudo supervisorctl status

# View logs
tail -f /var/log/supervisor/backend.err.log
tail -f /var/log/supervisor/frontend.err.log
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
4. **Test thoroughly**
5. **Commit your changes**
   ```bash
   git commit -m "Add your feature description"
   ```
6. **Push to the branch**
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Open a Pull Request**

**Code Style:**
- Follow existing code patterns
- Use descriptive variable and function names
- Add comments for complex logic
- Keep functions focused and modular

---

## 📚 Documentation

- **[frontend/README.md](frontend/README.md)** — Frontend-specific documentation including pages, routes, components, state management, and API client details
- **[backend/README.md](backend/README.md)** — Backend-specific documentation including API endpoints, data models, RBAC internals, and integration details
- **[memory/PRD.md](memory/PRD.md)** — Product Requirements Document with detailed feature specifications
- **[memory/wireframes.html](memory/wireframes.html)** — UI/UX wireframes and design mockups
- **[auth_testing.md](auth_testing.md)** — Authentication testing checklist and procedures
- **[test_result.md](test_result.md)** — Testing protocols, results, and history

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🆘 Support & Troubleshooting

### Common Issues

**Backend won't start:**
- Ensure MongoDB connection string is correct in `.env`
- Check that MongoDB Atlas IP whitelist includes your IP
- Verify all Python dependencies are installed

**Frontend can't connect to backend:**
- Check that `REACT_APP_BACKEND_URL` is set correctly
- Ensure backend is running on the expected port
- Check CORS configuration in backend `.env`

**Google OAuth not working:**
- Verify Google Cloud Console configuration
- Check that redirect URIs match your domain
- Ensure Emergent service is properly configured

**Images not uploading:**
- Verify Cloudinary credentials in `.env`
- Check Cloudinary upload presets and permissions
- Ensure network can reach Cloudinary servers

**Push notifications not working:**
- Verify VAPID keys are correctly configured
- Check browser supports push notifications
- Ensure service worker is properly registered

### Getting Help

- Check the documentation files listed above
- Review existing issues in the repository
- Create a new issue with detailed description of the problem
- Include error messages, environment details, and steps to reproduce

---

## 🎯 Roadmap

Future enhancements planned for AssetFlow Campus:

- [ ] Mobile app (React Native)
- [ ] Advanced analytics and reporting
- [ ] Integration with procurement systems
- [ ] Asset lifecycle automation
- [ ] Multi-campus support
- [ ] Enhanced offline capabilities
- [ ] Real-time collaboration features
- [ ] Advanced audit trails and compliance reporting

---

## 🙏 Acknowledgments

- Built with modern web technologies (React, FastAPI, MongoDB)
- UI components from shadcn/ui and Radix UI
- Icons from Lucide React
- Charts from Recharts
- PDF generation with ReportLab
- Image management with Cloudinary
- Push notifications with Web Push API

---

**Built with ❤️ for educational institutions**

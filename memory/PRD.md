# AssetFlow Campus PRD

## Original problem statement
Make sure every single function, every single button, and every single page should be working. Activity logs from checking every single logic should be correct in this project. UI guide from https://wope.com/; make sure it should also have dark and light mode.

## Architecture decisions
- React 19 frontend with React Router, shadcn-compatible primitives, Lucide icons, Sonner feedback, and responsive CSS.
- FastAPI backend with Motor and MongoDB using the protected MONGO_URL and DB_NAME environment variables.
- Cookie-based sessions with email/password accounts and Emergent-managed Google OAuth session exchange.
- Custom UUID-style user and entity IDs; recursive MongoDB-safe response cleaning; every successful mutation writes a structured activity event.

## User personas
- Asset Manager: registers, assigns, checks in/out, and maintains campus assets.
- Department coordinator or HOD: reviews operational status and utilization.
- Student or employee: signs in, views permitted inventory, and raises maintenance requests.
- Auditor or administrator: reviews activity history and reports.

## Core requirements (static)
- Complete campus asset visibility and lifecycle status.
- Authenticated workspace with email/password and Google sign-in.
- Searchable inventory, asset details, checkout/checkin, maintenance workflow, reports, and activity logs.
- Persistent, accurate activity history for state-changing actions.
- Wope-inspired structured workspace with accessible light and dark modes.
- Responsive desktop and mobile navigation with actionable feedback.

## What is implemented
- 2026-08-07: Replaced the starter screen with a complete AssetFlow Campus workspace and seeded realistic campus inventory/activity data.
- 2026-08-07: Added signup, login, logout, protected routes, Google OAuth callback exchange, and demo Asset Manager account.
- 2026-08-07: Added dashboard KPIs, inventory search/filter/register, asset detail, checkout/checkin, maintenance Kanban, reports, activity filters, theme persistence, and responsive shell.
- 2026-08-07: Fixed recursive activity serialization, activity error handling, OAuth callback mounting, and previously inactive top-bar controls.

- 2026-08-07: Added server-side non-blank validators for department/category names, booking purpose, and audit department/period fields (whitespace-only inputs now return 422).
- 2026-08-07: Fixed `react-hooks/exhaustive-deps` warnings in Inventory and AssetDetail by wrapping `load` in `useCallback`.

## Prioritized backlog
- P0: Add admin-only RBAC screens for organization setup, account approvals, and audit-cycle closure.
- P1: Add resource booking calendar with overlap validation and bundled resources.
- P1: Add no-dues clearance and accreditation export templates.
- P2: Add QR scanning, file/photo attachments, notifications preferences, and external messaging channels.

## Next tasks list
- Expand server-side role permissions beyond the current authenticated workspace.
- Add booking, audit, no-dues, and organization modules from the technical proposal.
- Add automated regression coverage for every mutation and role boundary.

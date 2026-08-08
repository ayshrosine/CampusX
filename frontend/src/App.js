import { useCallback, useEffect, useRef, useState } from "react";
import { BrowserRouter, Routes, Route, NavLink, useLocation, useNavigate, useParams } from "react-router-dom";
import { Activity, Archive, ArrowLeft, ArrowRight, BarChart3, Bell, Box, Camera, Check, ChevronRight, ClipboardCheck, Clock3, Download, Eye, FileText, GripVertical, Hammer, Image as ImageIcon, LayoutDashboard, LogOut, Menu, MoreHorizontal, Moon, Package, Plus, QrCode, Search, Settings2, Shield, Sun, Trash2, Upload, User, Users, Wrench, X, Zap } from "lucide-react";
import { Toaster, toast } from "sonner";
import { QRCodeSVG } from "qrcode.react";
import { Html5Qrcode } from "html5-qrcode";
import { DragDropContext, Droppable, Draggable } from "@hello-pangea/dnd";
import "@/App.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const api = async (path, options = {}) => {
  const res = await fetch(`${API}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data && data.detail;
    let msg = "Something went wrong";
    if (typeof detail === "string") msg = detail;
    else if (Array.isArray(detail)) msg = detail.map((d) => d.msg || d.message || JSON.stringify(d)).join("; ");
    else if (detail && typeof detail === "object") msg = detail.msg || JSON.stringify(detail);
    throw new Error(msg);
  }
  return data;
};

const nav = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, perm: null },
  { to: "/inventory", label: "Inventory", icon: Package, perm: null },
  { to: "/bookings", label: "Bookings", icon: Clock3, perm: "booking" },
  { to: "/maintenance", label: "Maintenance", icon: Wrench, perm: "maintenance_write" },
  { to: "/audits", label: "Audit Cycles", icon: ClipboardCheck, perm: "audit" },
  { to: "/nodues", label: "No-Dues", icon: Check, perm: "nodues" },
  { to: "/reports", label: "Reports", icon: BarChart3, perm: "reports" },
  { to: "/activity", label: "Activity Logs", icon: Activity, perm: null },
  { to: "/digest", label: "Weekly Digest", icon: FileText, perm: "admin" },
  { to: "/admin", label: "Admin Console", icon: Settings2, perm: "admin" },
];

// Cloudinary upload helper
async function uploadToCloudinary(file, folder) {
  const sig = await api(`/uploads/signature?folder=${encodeURIComponent(folder)}`);
  const form = new FormData();
  form.append("file", file);
  form.append("api_key", sig.api_key);
  form.append("timestamp", sig.timestamp);
  form.append("signature", sig.signature);
  form.append("folder", sig.folder);
  const res = await fetch(`https://api.cloudinary.com/v1_1/${sig.cloud_name}/image/upload`, { method: "POST", body: form });
  const data = await res.json();
  if (!res.ok || !data.secure_url) throw new Error(data.error?.message || "Upload failed");
  return { public_id: data.public_id, secure_url: data.secure_url, width: data.width, height: data.height };
}

const ROLE_PERMISSIONS = {
  Admin: new Set(["admin", "asset_write", "maintenance_write", "booking", "audit", "nodues", "reports"]),
  "Asset Manager": new Set(["asset_write", "maintenance_write", "booking", "audit", "reports"]),
  HOD: new Set(["asset_write", "maintenance_write", "booking", "reports"]),
  Employee: new Set(["maintenance_write", "booking", "reports"]),
  Student: new Set(["booking", "maintenance_write"]),
};

const fmt = (v) => v ? new Date(v).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";
const fmtRelative = (v) => {
  if (!v) return "—";
  const d = new Date(v);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
};

/* ============================================================
   Brand mark - custom SVG logo
   ============================================================ */
const LogoMark = ({ size = 28 }) => (
  <svg width={size} height={size} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="AssetFlow">
    <rect width="40" height="40" rx="8" fill="currentColor" />
    <path d="M11 28 L17 12 L23 28 M13.5 22 L20.5 22" stroke="var(--elev,#fff)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="28" cy="12" r="2.4" fill="var(--elev,#fff)" />
  </svg>
);

/* ============================================================
   Auth
   ============================================================ */
function AuthCallback() {
  const loc = useLocation(), nav = useNavigate(), once = useRef(false);
  useEffect(() => {
    if (once.current) return;
    once.current = true;
    const sid = new URLSearchParams(loc.hash.slice(1)).get("session_id");
    api("/auth/session", { method: "POST", headers: { "X-Session-ID": sid } })
      .then(() => nav("/dashboard", { replace: true }))
      .catch((e) => { toast.error(e.message); nav("/login", { replace: true }); });
  }, [loc, nav]);
  return <div className="auth-loading">Completing secure sign-in…</div>;
}

function AuthGate({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const loc = useLocation(), navHook = useNavigate();
  useEffect(() => {
    if (loc.hash.includes("session_id=")) { setLoading(false); return; }
    api("/auth/me").then(setUser).catch(() => setUser(false)).finally(() => setLoading(false));
  }, [loc.hash]);
  if (loading) return <div className="auth-loading">Loading AssetFlow…</div>;
  if (!user) { navHook("/login", { replace: true }); return null; }
  return (
    <Shell user={user} onLogout={() => api("/auth/logout", { method: "POST" }).then(() => navHook("/login"))}>
      {children}
    </Shell>
  );
}

function ThemeToggleButton({ dark, setDark, className = "theme-toggle" }) {
  return (
    <button data-testid="theme-toggle-button" className={className} onClick={() => setDark(!dark)} aria-label="Toggle theme">
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

function Login() {
  const navHook = useNavigate();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "demo@assetflow.edu", password: "Campus123!" });
  const [busy, setBusy] = useState(false);
  const [dark, setDark] = useState(localStorage.theme === "dark" || (!localStorage.theme && matchMedia("(prefers-color-scheme: dark)").matches));
  useEffect(() => { document.documentElement.classList.toggle("dark", dark); localStorage.theme = dark ? "dark" : "light"; }, [dark]);

  const submit = async (e) => {
    e.preventDefault(); setBusy(true);
    try {
      await api(mode === "login" ? "/auth/login" : "/auth/signup", { method: "POST", body: JSON.stringify(form) });
      navHook("/dashboard");
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const google = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(window.location.origin + "/dashboard")}`;
  };

  return (
    <main className="auth-page">
      <div className="auth-nav">
        <div className="brand"><span style={{ color: "var(--ink)" }}><LogoMark size={26} /></span> AssetFlow</div>
        <ThemeToggleButton dark={dark} setDark={setDark} />
      </div>
      <div className="auth-wrap">
        <form className="auth-card" onSubmit={submit}>
          <p className="eyebrow">CAMPUS OS · v1.0</p>
          <h2 className="auth-title">{mode === "login" ? "Sign in to AssetFlow" : "Create your workspace"}</h2>
          <p className="auth-sub">{mode === "login" ? "Every asset. Accountable. From one calm workspace." : "New accounts start as Student and are approved by an admin."}</p>
          {mode !== "login" && (
            <input data-testid="signup-name-input" className="auth-input" placeholder="Full name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          )}
          <input data-testid="auth-email-input" className="auth-input" type="email" placeholder="College email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          <input data-testid="auth-password-input" className="auth-input" type="password" placeholder="Password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          <button data-testid="auth-submit-button" className="btn-pill" disabled={busy}>{busy ? "Working…" : mode === "login" ? "Continue" : "Create account"}<ArrowRight size={16} /></button>
          <div className="auth-divider">or continue with</div>
          <button data-testid="google-signin-button" type="button" className="btn-ghost-pill" onClick={google}>
            <svg width="16" height="16" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09Z" /><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23Z" /><path fill="#FBBC05" d="M5.84 14.09A6.98 6.98 0 0 1 5.47 12c0-.73.13-1.43.36-2.09V7.07H2.18A11 11 0 0 0 1 12c0 1.77.42 3.45 1.18 4.93l3.66-2.84Z" /><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38Z" /></svg>
            <span>Continue with Google</span>
          </button>
          <button data-testid="auth-mode-toggle-button" type="button" className="text-link" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
            {mode === "login" ? <>New here? <em>Create an account</em></> : <>Already have an account? <em>Sign in</em></>}
          </button>
          <div className="demo-tag">Demo · demo@assetflow.edu / Campus123!</div>
        </form>
      </div>
    </main>
  );
}

/* ============================================================
   Notifications
   ============================================================ */
function Notifications({ user, open, onClose }) {
  const [data, setData] = useState({ items: [], unread: 0 });
  const navHook = useNavigate();
  useEffect(() => {
    if (!open) return;
    api("/notifications").then(setData).catch((e) => toast.error(e.message));
    api("/notifications/mark-all-read", { method: "POST" }).catch(() => {});
  }, [open]);
  if (!open) return null;
  const kindIcons = { maintenance: <Wrench size={14} />, booking: <Clock3 size={14} />, approval: <Users size={14} />, audit: <ClipboardCheck size={14} /> };
  return (
    <>
      <div className="scrim" style={{ display: "block", background: "transparent" }} onClick={onClose} />
      <div className="notif-drawer" data-testid="notifications-drawer">
        <div className="notif-head">
          <h3>Notifications</h3>
          <button className="icon-btn" style={{ width: 28, height: 28 }} onClick={onClose} aria-label="Close notifications"><X size={14} /></button>
        </div>
        <div className="notif-body">
          {data.items.length === 0 ? (
            <div className="notif-empty">You’re all caught up.</div>
          ) : data.items.map((n) => (
            <div className="notif-row" data-testid="notification-row" key={n.id} onClick={() => { onClose(); navHook(n.link); }}>
              <div className={`kind-icon ${n.kind}`}>{kindIcons[n.kind] || <Bell size={14} />}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <b>{n.title}</b>
                <p>{n.detail}</p>
                <small>{fmtRelative(n.when)}</small>
              </div>
            </div>
          ))}
        </div>
        <div className="notif-foot">
          <small style={{ color: "var(--mute)", fontFamily: "var(--font-mono)", fontSize: 11 }}>{data.items.length} items</small>
          <button className="link-btn" onClick={() => { onClose(); navHook("/activity"); }}>View all activity <ArrowRight size={13} /></button>
        </div>
      </div>
    </>
  );
}

/* ============================================================
   Role Preview modal
   ============================================================ */
function RolePreviewModal({ onClose }) {
  const [role, setRole] = useState("Student");
  const [data, setData] = useState(null);
  useEffect(() => { api(`/admin/role-preview/${role}`).then(setData).catch((e) => toast.error(e.message)); }, [role]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()} data-testid="role-preview-modal">
        <div className="modal-title">
          <div>
            <p className="eyebrow">ROLE PLAYGROUND</p>
            <h2>Preview a role</h2>
            <p className="muted" style={{ margin: "4px 0 0" }}>Choose a role to see the exact workspace and capabilities that account would get.</p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close" data-testid="role-preview-close"><X size={16} /></button>
        </div>
        <select data-testid="role-preview-select" value={role} onChange={(e) => setRole(e.target.value)} style={{ height: 42 }}>
          {["Student", "Employee", "HOD", "Asset Manager", "Admin"].map((r) => <option key={r}>{r}</option>)}
        </select>
        {data && (
          <>
            <div>
              <p className="eyebrow">Visible pages ({data.visible_pages.length})</p>
              <div className="role-preview-grid">
                {data.visible_pages.map((p) => (
                  <div className="role-cap" key={p} data-testid="role-visible-page">
                    <b>{p.replace("/", "").replace(/^\w/, (c) => c.toUpperCase()) || "Home"}</b>
                    <span className="mono">{p}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="eyebrow">Capabilities ({data.capabilities.length})</p>
              <div className="role-preview-grid">
                {data.capabilities.length === 0 && <div className="role-cap">Read-only workspace</div>}
                {data.capabilities.map((c, i) => <div className="role-cap" key={i} data-testid="role-capability">{c}</div>)}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Shell
   ============================================================ */
function Shell({ user, onLogout, children }) {
  const [dark, setDark] = useState(localStorage.theme === "dark" || (!localStorage.theme && matchMedia("(prefers-color-scheme: dark)").matches));
  const [mobile, setMobile] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [rolePreviewFor, setRolePreviewFor] = useState(null);
  const previewRole = rolePreviewFor || user.role;

  useEffect(() => { document.documentElement.classList.toggle("dark", dark); localStorage.theme = dark ? "dark" : "light"; }, [dark]);
  useEffect(() => {
    const fetchUnread = () => api("/notifications").then((d) => setUnread(d.unread || 0)).catch(() => {});
    fetchUnread();
    const t = setInterval(fetchUnread, 60000);
    return () => clearInterval(t);
  }, []);

  const [previewOpen, setPreviewOpen] = useState(false);
  const visibleNav = nav.filter((x) => !x.perm || (ROLE_PERMISSIONS[previewRole] || new Set()).has(x.perm));

  return (
    <div className="app-shell">
      <aside className={mobile ? "sidebar open" : "sidebar"} data-testid="sidebar">
        <div className="brand"><span style={{ color: "var(--ink)" }}><LogoMark size={26} /></span> AssetFlow</div>
        <p className="workspace-label">Campus workspace</p>
        <nav>
          {visibleNav.map(({ to, label, icon: Icon }) => (
            <NavLink data-testid={`nav-${label.toLowerCase().replaceAll(" ", "-")}`} key={to} to={to} onClick={() => setMobile(false)} className={({ isActive }) => isActive ? "active" : ""}>
              <Icon size={16} />{label}
            </NavLink>
          ))}
        </nav>
        {rolePreviewFor && (
          <button className="sidebar-action" data-testid="clear-role-preview" onClick={() => setRolePreviewFor(null)} style={{ marginTop: 8, color: "var(--violet)" }}>
            <Eye size={14} /> Previewing as {rolePreviewFor} · exit
          </button>
        )}
        <div className="sidebar-bottom">
          <NavLink data-testid="scan-nav-button" to="/scan" className="sidebar-action" onClick={() => setMobile(false)}>
            <QrCode size={14} /> Scan asset
          </NavLink>
          {user.role === "Admin" && (
            <button data-testid="open-role-preview" className="sidebar-action" onClick={() => setPreviewOpen(true)}>
              <Shield size={14} /> Role playground
            </button>
          )}
          <button data-testid="logout-button" className="sidebar-action" onClick={onLogout}><LogOut size={14} /> Log out</button>
        </div>
      </aside>
      {mobile && <div className="scrim" onClick={() => setMobile(false)} />}
      <section className="main-area">
        <header className="topbar">
          <button data-testid="mobile-menu-button" className="icon-btn mobile-menu" onClick={() => setMobile(true)}><Menu size={16} /></button>
          <div className="breadcrumbs"><span>Workspace</span><ChevronRight size={12} /><strong>{window.location.pathname.split("/")[1] || "Dashboard"}</strong>{rolePreviewFor && <span className="role-badge"><Eye size={11} /> Previewing {rolePreviewFor}</span>}</div>
          <div className="top-actions">
            <button data-testid="global-search-button" className="search-trigger" onClick={() => toast.info("Search is available from Inventory")}><Search size={13} /> Search <kbd>⌘K</kbd></button>
            <ThemeToggleButton dark={dark} setDark={setDark} className="icon-btn" />
            <button data-testid="notifications-button" className="icon-btn" onClick={() => setNotifOpen(true)} aria-label="Notifications">
              <Bell size={16} />
              {unread > 0 && <span className="badge" data-testid="notifications-badge">{unread}</span>}
            </button>
            <div className="user-chip"><span>{user.name.split(" ").map((x) => x[0]).join("").slice(0, 2)}</span><div><b>{user.name}</b><small>{user.role}</small></div></div>
          </div>
        </header>
        <main className="page-content">{children}</main>
      </section>
      <Notifications user={user} open={notifOpen} onClose={() => setNotifOpen(false)} />
      {previewOpen && <RolePreviewModal onClose={() => setPreviewOpen(false)} />}
    </div>
  );
}

function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="muted">{description}</p>
      </div>
      {action}
    </div>
  );
}

function Status({ children }) {
  const v = String(children || "").toLowerCase().replaceAll(" ", "-");
  return <span className={`status status-${v}`}><i />{children}</span>;
}

/* ============================================================
   Pages
   ============================================================ */
function Dashboard() {
  const [data, setData] = useState(null);
  useEffect(() => { api("/dashboard").then(setData).catch((e) => toast.error(e.message)); }, []);
  if (!data) return <div className="loading">Loading dashboard…</div>;
  const metrics = [
    ["Total assets", data.kpis.total_assets, "Across all departments", Box],
    ["Available", data.kpis.available, "Ready to allocate", Check],
    ["Open maintenance", data.kpis.maintenance, "Needs attention", Wrench],
    ["Utilization", `${data.kpis.utilization}%`, "This month", BarChart3],
  ];
  return (
    <>
      <PageHeader eyebrow={new Date().toLocaleDateString([], { weekday: "long", month: "long", day: "numeric", year: "numeric" }).toUpperCase()} title={<>Welcome back, <em>{data.user.name.split(" ")[0]}.</em></>} description="Here’s what’s happening across your campus workspace." action={<NavLink data-testid="dashboard-add-asset-button" className="primary-btn" to="/inventory?new=1"><Plus size={14} /> Add asset</NavLink>} />
      <div className="metric-grid">
        {metrics.map(([label, value, sub, Icon]) => (
          <div className="metric" data-testid={`dashboard-metric-${label.toLowerCase().replaceAll(" ", "-")}`} key={label}>
            <div className="metric-top"><span>{label}</span><Icon size={16} /></div>
            <strong>{value}</strong>
            <small>{sub}</small>
          </div>
        ))}
      </div>
      <div className="dashboard-grid">
        <section className="surface chart-surface">
          <div className="section-title"><div><p className="eyebrow">ACTIVITY OVERVIEW</p><h3>Campus operations</h3></div><span className="chart-legend"><i /> Assets touched</span></div>
          <div className="chart">
            <div className="chart-y"><span>40</span><span>30</span><span>20</span><span>10</span><span>0</span></div>
            <div className="chart-bars">
              {[18, 35, 24, 42, 31, 39, 28, 48, 35, 44, 52, 41].map((h, i) => (
                <div className="bar-wrap" key={i}>
                  <div className="bar" style={{ height: `${h}%` }} />
                  <small>{["May 27", "Jun 3", "Jun 10", "Jun 17", "Jun 24", "Jul 1", "Jul 8", "Jul 15", "Jul 22", "Jul 29", "Aug 5", "Aug 12"][i]}</small>
                </div>
              ))}
            </div>
          </div>
        </section>
        <section className="surface">
          <div className="section-title"><div><p className="eyebrow">LIVE FEED</p><h3>Recent activity</h3></div><NavLink data-testid="dashboard-view-activity-link" to="/activity" className="link-btn">View all <ArrowRight size={13} /></NavLink></div>
          {data.activity.map((x, i) => (
            <div data-testid="dashboard-activity-row" className="activity-row" key={x.event_id || i}>
              <span className="activity-icon"><Activity size={13} /></span>
              <div><b>{x.actor}</b> {x.action}<small>{fmt(x.timestamp)} · {x.entity_type}</small></div>
            </div>
          ))}
        </section>
      </div>
    </>
  );
}

function Inventory() {
  const [assets, setAssets] = useState([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("All");
  const [show, setShow] = useState(false);
  const [newAsset, setNewAsset] = useState({ name: "", category: "IT Equipment", location: "", department: "Computer Science" });
  const load = useCallback(() => api(`/assets?search=${encodeURIComponent(search)}&status=${status}`).then(setAssets).catch((e) => toast.error(e.message)), [search, status]);
  useEffect(() => { load(); }, [load]);
  const save = async (e) => {
    e.preventDefault();
    try {
      await api("/assets", { method: "POST", body: JSON.stringify(newAsset) });
      toast.success("Asset registered and logged");
      setShow(false);
      setNewAsset({ name: "", category: "IT Equipment", location: "", department: "Computer Science" });
      load();
    } catch (err) { toast.error(err.message); }
  };
  return (
    <>
      <PageHeader eyebrow="ASSET DIRECTORY" title="Inventory" description={`${assets.length} assets in your campus workspace.`} action={<button data-testid="inventory-add-asset-button" className="primary-btn" onClick={() => setShow(true)}><Plus size={14} /> Register asset</button>} />
      <div className="toolbar">
        <div className="search-box"><Search size={14} /><input data-testid="asset-inventory-search-input" placeholder="Search by name, tag, serial…" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <select data-testid="asset-status-filter" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option>All</option><option>Available</option><option>Allocated</option><option>Under Maintenance</option>
        </select>
        <NavLink to="/scan" className="secondary-btn compact" data-testid="inventory-scan-link"><QrCode size={13} /> Scan</NavLink>
      </div>
      <section className="surface table-surface">
        <div className="table-head"><span>ASSET</span><span>TAG / SERIAL</span><span>LOCATION</span><span>STATUS</span><span>UPDATED</span><span /></div>
        {assets.map((a) => (
          <NavLink data-testid="asset-inventory-row" to={`/inventory/${a.asset_id}`} className="table-row" key={a.asset_id}>
            <div className="asset-name"><span className="asset-symbol"><Package size={14} /></span><div><b>{a.name}</b><small>{a.category}</small></div></div>
            <div className="mono">{a.tag}<small>{a.serial}</small></div>
            <div>{a.location}<small>{a.department}</small></div>
            <div><Status>{a.status}</Status></div>
            <div className="muted">{fmt(a.updated_at)}</div>
            <ChevronRight size={16} />
          </NavLink>
        ))}
        {!assets.length && <div className="empty">No assets match those filters.</div>}
      </section>
      {show && (
        <div className="modal-backdrop" onClick={() => setShow(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={save}>
            <div className="modal-title">
              <div><p className="eyebrow">NEW RECORD</p><h2>Register an asset</h2></div>
              <button data-testid="close-asset-modal-button" type="button" className="icon-btn" onClick={() => setShow(false)}><X size={14} /></button>
            </div>
            {[["name", "Asset name"], ["location", "Location"], ["department", "Department"]].map(([key, label]) => (
              <input data-testid={`new-asset-${key}-input`} key={key} placeholder={label} value={newAsset[key]} onChange={(e) => setNewAsset({ ...newAsset, [key]: e.target.value })} required />
            ))}
            <select data-testid="new-asset-category-select" value={newAsset.category} onChange={(e) => setNewAsset({ ...newAsset, category: e.target.value })}>
              <option>IT Equipment</option><option>Lab Equipment</option><option>Workshop Machinery</option><option>Sports Gear</option>
            </select>
            <button data-testid="register-asset-submit-button" className="primary-btn">Register asset <Check size={13} /></button>
          </form>
        </div>
      )}
    </>
  );
}

function AssetDetail() {
  const { asset_id } = useParams(), navHook = useNavigate();
  const [data, setData] = useState(null);
  const [holder, setHolder] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api(`/assets/${asset_id}`).then(setData), [asset_id]);
  useEffect(() => { load(); }, [load]);
  if (!data) return <div className="loading">Loading asset…</div>;
  const mutate = async (path, body) => {
    setBusy(true);
    try {
      await api(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
      toast.success("Asset updated and activity logged");
      load();
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  const qrValue = `${window.location.origin}/scan?tag=${encodeURIComponent(data.asset.tag)}`;
  return (
    <>
      <button data-testid="asset-detail-back-button" className="back-btn" onClick={() => navHook("/inventory")}><ArrowLeft size={13} /> Back to inventory</button>
      <PageHeader eyebrow="ASSET DETAIL" title={data.asset.name} description={<span className="mono">{data.asset.tag} · {data.asset.serial}</span>} action={<Status>{data.asset.status}</Status>} />
      <div className="detail-grid">
        <section className="surface">
          <div className="detail-hero">
            <span className="large-symbol"><Package size={22} /></span>
            <div><p className="eyebrow">CURRENT LOCATION</p><h3>{data.asset.location}</h3><p className="muted">{data.asset.department} · {data.asset.category}</p></div>
          </div>
          <div className="detail-fields">
            <div><small>ASSET TAG</small><b className="mono">{data.asset.tag}</b></div>
            <div><small>SERIAL</small><b className="mono">{data.asset.serial}</b></div>
            <div><small>BOOKABLE</small><b>{data.asset.bookable ? "Yes" : "No"}</b></div>
            <div><small>LAST UPDATED</small><b>{fmt(data.asset.updated_at)}</b></div>
          </div>
        </section>
        <aside className="surface action-panel">
          <p className="eyebrow">QUICK ACTIONS</p>
          {data.asset.status === "Available" ? (
            <>
              <input data-testid="checkout-holder-input" placeholder="Assign to…" value={holder} onChange={(e) => setHolder(e.target.value)} />
              <button data-testid="asset-checkout-button" className="primary-btn" disabled={!holder || busy} onClick={() => mutate(`/assets/${asset_id}/checkout`, { holder })}><ClipboardCheck size={14} /> Check out</button>
            </>
          ) : (
            <button data-testid="asset-checkin-button" className="primary-btn" disabled={busy} onClick={() => mutate(`/assets/${asset_id}/checkin`)}><Check size={14} /> Check in</button>
          )}
          <NavLink data-testid="asset-maintenance-link" to="/maintenance" className="secondary-btn"><Wrench size={13} /> Raise maintenance</NavLink>
          <div className="qr-panel" data-testid="asset-qr-panel">
            <QRCodeSVG value={qrValue} size={128} bgColor="transparent" fgColor="currentColor" level="M" />
            <small>Scan on mobile to check in/out</small>
          </div>
        </aside>
      </div>
      <section className="surface">
        <div className="section-title"><div><p className="eyebrow">AUDIT TRAIL</p><h3>Asset history</h3></div><span className="muted">{data.history.length} events</span></div>
        {data.history.map((x) => (
          <div data-testid="asset-history-event-row" className="history-row" key={x.event_id}>
            <span className="activity-icon"><Activity size={13} /></span>
            <div><b>{x.action}</b><small>{x.actor} · {fmt(x.timestamp)}</small></div>
            <span className="mono muted">{x.entity_type}</span>
          </div>
        ))}
      </section>
    </>
  );
}

function PhotoStrip({ photos, onRemove, canDelete = true }) {
  if (!photos || photos.length === 0) return null;
  return (
    <div className="photo-strip" data-testid="photo-strip">
      {photos.map((p) => (
        <div className="photo-thumb" key={p.public_id}>
          <a href={p.url} target="_blank" rel="noreferrer"><img src={p.url.replace("/upload/", "/upload/w_180,h_180,c_fill,q_auto,f_auto/")} alt={p.public_id} loading="lazy" /></a>
          {canDelete && onRemove && (
            <button data-testid="photo-remove-button" className="photo-remove" onClick={(e) => { e.stopPropagation(); onRemove(p); }} aria-label="Remove photo"><X size={11} /></button>
          )}
        </div>
      ))}
    </div>
  );
}

function PhotoUploadButton({ folder, onUploaded, label = "Attach photo", testId = "photo-upload-button" }) {
  const [busy, setBusy] = useState(false);
  const ref = useRef(null);
  const onPick = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) { toast.error("Please pick an image"); return; }
    if (file.size > 8 * 1024 * 1024) { toast.error("Image too large (max 8 MB)"); return; }
    setBusy(true);
    try {
      const uploaded = await uploadToCloudinary(file, folder);
      await onUploaded(uploaded);
      toast.success("Photo uploaded");
    } catch (err) { toast.error(err.message); } finally { setBusy(false); if (ref.current) ref.current.value = ""; }
  };
  return (
    <>
      <input ref={ref} type="file" accept="image/*" hidden onChange={onPick} data-testid={`${testId}-input`} />
      <button type="button" className="advance-btn" data-testid={testId} disabled={busy} onClick={() => ref.current?.click()} style={{ width: "auto", marginTop: 0, padding: "6px 10px" }}>
        {busy ? <>Uploading…</> : <><Upload size={12} /> {label}</>}
      </button>
    </>
  );
}

function MaintenanceCard({ x, stage, onAdvance, onSetStatus, onDelete, onAttach, onRemovePhoto, isDragging, dragProps }) {
  const [openMenu, setOpenMenu] = useState(false);
  const stages = ["Pending", "Approved", "In progress", "Resolved"];
  const idx = stages.indexOf(stage);
  return (
    <div data-testid="maintenance-request-card" className={`work-card ${isDragging ? "dragging" : ""}`} {...(dragProps || {})}>
      <div className="work-card-top">
        <Status>{x.priority}</Status>
        <span className="mono" style={{ color: "var(--mute)" }}>{x.request_id}</span>
      </div>
      <h3>{x.description}</h3>
      <p className="muted" style={{ fontSize: 12 }}>{x.asset_id} · {x.raised_by}</p>
      <small className="mono" style={{ color: "var(--mute)", fontSize: 10 }}>{fmt(x.created_at)}</small>
      <PhotoStrip photos={x.photos} onRemove={(p) => onRemovePhoto(x, p)} />
      <div style={{ display: "flex", gap: 6, marginTop: 12, position: "relative", flexWrap: "wrap" }}>
        {stage !== "Resolved" && stage !== "Rejected" && idx < 3 && (
          <button data-testid="maintenance-advance-button" className="advance-btn" style={{ flex: 1, marginTop: 0 }} onClick={() => onAdvance(x, stages[idx + 1])}>Advance <ChevronRight size={12} /></button>
        )}
        <PhotoUploadButton folder={`assetflow/maintenance/${x.request_id}`} onUploaded={(u) => onAttach(x, u)} label={<ImageIcon size={12} />} testId="maintenance-photo-upload" />
        <button data-testid="maintenance-menu-button" className="advance-btn" style={{ width: 32, marginTop: 0, padding: 0 }} onClick={(e) => { e.stopPropagation(); setOpenMenu((v) => !v); }} aria-label="More actions"><MoreHorizontal size={14} /></button>
        {openMenu && (
          <>
            <div style={{ position: "fixed", inset: 0, zIndex: 8 }} onClick={() => setOpenMenu(false)} />
            <div className="menu-popover" data-testid="maintenance-menu-popover">
              {stage !== "Resolved" && idx < 3 && <button data-testid="menu-move-next" onClick={() => { setOpenMenu(false); onAdvance(x, stages[idx + 1]); }}><ArrowRight size={13} /> Move to next stage</button>}
              {stage !== "Resolved" && <button data-testid="menu-move-resolved" onClick={() => { setOpenMenu(false); onSetStatus(x, "Resolved"); }}><Check size={13} /> Mark resolved</button>}
              {stage !== "Rejected" && <button data-testid="menu-reject" onClick={() => { setOpenMenu(false); onSetStatus(x, "Rejected"); }}><X size={13} /> Reject</button>}
              <button data-testid="menu-delete" className="danger" onClick={() => { setOpenMenu(false); onDelete(x); }}><Trash2 size={13} /> Delete</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Maintenance() {
  const [items, setItems] = useState([]);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ asset_id: "ast_seed_2", description: "", priority: "Medium" });
  const load = useCallback(() => api("/maintenance").then(setItems), []);
  useEffect(() => { load(); }, [load]);
  const save = async (e) => {
    e.preventDefault();
    try {
      await api("/maintenance", { method: "POST", body: JSON.stringify(form) });
      toast.success("Request raised and logged"); setShow(false); load();
    } catch (err) { toast.error(err.message); }
  };
  const setStatus = async (x, status) => {
    if (x.status === status) return;
    try {
      await api(`/maintenance/${x.request_id}`, { method: "PATCH", body: JSON.stringify({ status }) });
      toast.success(`Moved to ${status}`); load();
    } catch (e) { toast.error(e.message); }
  };
  const remove = async (x) => {
    if (!window.confirm(`Delete request "${x.description}"?`)) return;
    try {
      await api(`/maintenance/${x.request_id}`, { method: "DELETE" });
      toast.success("Request removed"); load();
    } catch (e) { toast.error(e.message); }
  };
  const attach = async (x, uploaded) => {
    try {
      await api(`/maintenance/${x.request_id}/photos`, { method: "POST", body: JSON.stringify(uploaded) });
      load();
    } catch (e) { toast.error(e.message); }
  };
  const removePhoto = async (x, p) => {
    if (!window.confirm("Remove this photo?")) return;
    try {
      await api(`/maintenance/${x.request_id}/photos/${encodeURIComponent(p.public_id)}`, { method: "DELETE" });
      toast.success("Photo removed"); load();
    } catch (e) { toast.error(e.message); }
  };
  const stages = ["Pending", "Approved", "In progress", "Resolved"];
  const onDragEnd = (result) => {
    if (!result.destination) return;
    const item = items.find((i) => i.request_id === result.draggableId);
    if (!item) return;
    const target = result.destination.droppableId;
    if (item.status === target) return;
    setStatus(item, target);
  };
  return (
    <>
      <PageHeader eyebrow="WORK ORDER QUEUE" title="Maintenance" description="Drag cards between columns, use the menu for more actions. Resolved items auto-delete after 30 days." action={<button data-testid="maintenance-new-request-button" className="primary-btn" onClick={() => setShow(true)}><Plus size={14} /> Raise request</button>} />
      <DragDropContext onDragEnd={onDragEnd}>
        <div className="kanban">
          {stages.map((stage) => (
            <Droppable droppableId={stage} key={stage}>
              {(dropProvided, dropSnapshot) => (
                <section className={`kanban-column ${dropSnapshot.isDraggingOver ? "over" : ""}`} ref={dropProvided.innerRef} {...dropProvided.droppableProps} data-testid={`kanban-column-${stage.toLowerCase().replaceAll(" ", "-")}`}>
                  <div className="kanban-title">
                    <span><i className={`stage-dot ${stage.toLowerCase().replaceAll(" ", "-")}`} />{stage}</span>
                    <b>{items.filter((x) => x.status === stage).length}</b>
                  </div>
                  {items.filter((x) => x.status === stage).map((x, idx) => (
                    <Draggable key={x.request_id} draggableId={x.request_id} index={idx}>
                      {(dragProvided, dragSnapshot) => (
                        <div ref={dragProvided.innerRef} {...dragProvided.draggableProps}>
                          <MaintenanceCard
                            x={x}
                            stage={stage}
                            onAdvance={setStatus}
                            onSetStatus={setStatus}
                            onDelete={remove}
                            onAttach={attach}
                            onRemovePhoto={removePhoto}
                            isDragging={dragSnapshot.isDragging}
                            dragProps={{ ...dragProvided.dragHandleProps }}
                          />
                        </div>
                      )}
                    </Draggable>
                  ))}
                  {dropProvided.placeholder}
                </section>
              )}
            </Droppable>
          ))}
        </div>
      </DragDropContext>
      {items.some((x) => x.status === "Rejected") && (
        <section className="surface" style={{ marginTop: 16 }}>
          <div className="section-title"><div><p className="eyebrow">REJECTED</p><h3>Closed without action</h3></div></div>
          {items.filter((x) => x.status === "Rejected").map((x) => (
            <div className="log-row" key={x.request_id}>
              <span className="activity-icon"><X size={13} /></span>
              <div><b>{x.description}</b><small>{x.asset_id} · {x.raised_by} · {fmt(x.rejected_at || x.created_at)}</small></div>
              <button className="advance-btn" style={{ width: "auto", marginTop: 0, padding: "4px 10px" }} onClick={() => setStatus(x, "Pending")}>Reopen</button>
              <button className="advance-btn" style={{ width: "auto", marginTop: 0, padding: "4px 10px" }} onClick={() => remove(x)}><Trash2 size={12} /></button>
            </div>
          ))}
        </section>
      )}
      {show && (
        <div className="modal-backdrop" onClick={() => setShow(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={save}>
            <div className="modal-title"><div><p className="eyebrow">WORK ORDER</p><h2>Raise maintenance</h2></div><button data-testid="close-maintenance-modal-button" type="button" className="icon-btn" onClick={() => setShow(false)}><X size={14} /></button></div>
            <input data-testid="maintenance-asset-id-input" placeholder="Asset ID" value={form.asset_id} onChange={(e) => setForm({ ...form, asset_id: e.target.value })} />
            <textarea data-testid="maintenance-description-input" placeholder="What needs attention?" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required />
            <select data-testid="maintenance-priority-select" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
              <option>Low</option><option>Medium</option><option>High</option>
            </select>
            <button data-testid="maintenance-submit-button" className="primary-btn">Raise request <Wrench size={13} /></button>
          </form>
        </div>
      )}
    </>
  );
}

function ActivityPage() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("All");
  const [error, setError] = useState("");
  useEffect(() => { api("/activity").then(setItems).catch((e) => setError(e.message)); }, []);
  const kindOf = (x) => {
    if (["maintenance", "audit"].includes(x.entity_type)) return "Alerts";
    if (["user", "department", "category", "report"].includes(x.entity_type)) return "Approvals";
    if (x.entity_type === "booking") return "Bookings";
    return "Other";
  };
  const visible = filter === "All" ? items : items.filter((x) => kindOf(x) === filter);
  const tabs = ["All", "Alerts", "Approvals", "Bookings"];
  return (
    <>
      <PageHeader eyebrow="SYSTEM OF RECORD" title="Activity logs" description="A persistent, reviewable history of every successful workspace action." />
      <div className="tabs">
        {tabs.map((t) => (
          <button data-testid={`activity-filter-${t.toLowerCase()}`} className={filter === t ? "selected" : ""} onClick={() => setFilter(t)} key={t}>{t}</button>
        ))}
      </div>
      {error ? <div data-testid="activity-log-error" className="empty">Unable to load activity logs. {error}</div> : (
        <section className="surface log-list">
          {visible.map((x) => (
            <div data-testid="activity-log-event-row" className="log-row" key={x.event_id}>
              <span className="activity-icon"><Activity size={13} /></span>
              <div><b>{x.actor}</b><p style={{ margin: "2px 0" }}>{x.action} <span className="mono">{x.entity_id}</span></p><small>{fmt(x.timestamp)} · {x.entity_type}</small></div>
              <ChevronRight size={14} />
            </div>
          ))}
          {!visible.length && !error && <div className="empty">No matching activity.</div>}
        </section>
      )}
    </>
  );
}

function Reports() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api("/reports").then(setData); }, []);
  if (!data) return <div className="loading">Loading reports…</div>;
  const download = async (format) => {
    setBusy(true);
    try {
      const res = await fetch(`${API}/reports/accreditation/download?format=${format}`, { credentials: "include" });
      if (!res.ok) throw new Error("Download failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `assetflow_accreditation.${format}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success(`Report downloaded as ${format.toUpperCase()}`);
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <>
      <PageHeader eyebrow="CAMPUS INTELLIGENCE" title="Reports & analytics" description="A clear view of utilization, ownership, and operational load." action={
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button data-testid="report-download-csv" className="secondary-btn" disabled={busy} onClick={() => download("csv")}><Download size={13} /> CSV</button>
          <button data-testid="report-download-pdf" className="primary-btn" disabled={busy} onClick={() => download("pdf")}><FileText size={13} /> PDF</button>
        </div>
      } />
      <div className="metric-grid">
        <div className="metric"><div className="metric-top"><span>Total tracked</span><Box size={16} /></div><strong>{data.total}</strong><small>Across all departments</small></div>
        {Object.entries(data.status_counts).slice(0, 3).map(([k, v]) => (
          <div className="metric" key={k}><div className="metric-top"><span>{k}</span><Activity size={16} /></div><strong>{v}</strong><small>Current inventory</small></div>
        ))}
      </div>
      <section className="surface report-table">
        <div className="section-title"><div><p className="eyebrow">UTILIZATION BY DEPARTMENT</p><h3>Where resources are moving</h3></div></div>
        {data.departments.map((x) => {
          const pct = x.total ? Math.round((x.allocated / x.total) * 100) : 0;
          return (
            <div data-testid="report-department-row" className="report-row" key={x.name}>
              <div><b>{x.name}</b><small>{x.allocated} of {x.total}</small></div>
              <div className="progress"><span style={{ width: `${pct}%` }} /></div>
              <strong>{pct}%</strong>
            </div>
          );
        })}
      </section>
    </>
  );
}

function Bookings() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ resource_id: "ast_seed_1", date: new Date(Date.now() + 86400000).toISOString().slice(0, 10), start_time: "10:00", end_time: "11:00", purpose: "" });
  const load = useCallback(() => api("/bookings").then(setItems).catch((e) => toast.error(e.message)), []);
  useEffect(() => { load(); }, [load]);
  const save = async (e) => {
    e.preventDefault();
    try {
      await api("/bookings", { method: "POST", body: JSON.stringify(form) });
      toast.success("Booking confirmed and logged");
      load();
    } catch (e) { toast.error(e.message); }
  };
  const cancel = async (b) => {
    try {
      await api(`/bookings/${b.booking_id}`, { method: "DELETE" });
      toast.success("Booking cancelled");
      load();
    } catch (e) { toast.error(e.message); }
  };
  return (
    <>
      <PageHeader eyebrow="RESOURCE CALENDAR" title="Bookings" description="Reserve shared rooms and equipment without double-booking." action={<button data-testid="booking-submit-button" className="primary-btn" onClick={() => document.getElementById("booking-form").requestSubmit()}><Plus size={14} /> Confirm booking</button>} />
      <section className="surface form-surface">
        <p className="eyebrow" style={{ marginBottom: 10 }}>NEW SLOT</p>
        <form id="booking-form" className="inline-form" onSubmit={save}>
          {[["resource_id", "Resource ID"], ["date", "Date"], ["start_time", "Start"], ["end_time", "End"], ["purpose", "Purpose"]].map(([k, p]) => (
            <input data-testid={`booking-${k}-input`} key={k} placeholder={p} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} required />
          ))}
        </form>
      </section>
      <section className="surface">
        <div className="section-title"><div><p className="eyebrow">CONFIRMED SLOTS</p><h3>Upcoming bookings</h3></div></div>
        {items.map((x) => (
          <div data-testid="booking-row" className="log-row" key={x.booking_id}>
            <span className="activity-icon"><Clock3 size={13} /></span>
            <div><b>{x.resource_id}</b><p style={{ margin: "2px 0", fontSize: 12 }}>{x.date} · {x.start_time}–{x.end_time}</p><small>{x.requested_by} · {x.purpose}</small></div>
            <Status>{x.status}</Status>
            <button data-testid="booking-cancel-button" className="advance-btn" style={{ width: "auto", padding: "4px 10px", marginTop: 0 }} onClick={() => cancel(x)}><X size={12} /> Cancel</button>
          </div>
        ))}
        {!items.length && <div className="empty">No confirmed bookings yet.</div>}
      </section>
    </>
  );
}

function Audits() {
  const [items, setItems] = useState([]);
  const [department, setDepartment] = useState("Computer Science");
  const [period, setPeriod] = useState("August 2026");
  const load = useCallback(() => api("/audits").then(setItems).catch((e) => toast.error(e.message)), []);
  useEffect(() => { load(); }, [load]);
  const create = async () => {
    try {
      await api("/audits", { method: "POST", body: JSON.stringify({ department, period, auditors: ["Maya Iyer"] }) });
      toast.success("Audit cycle opened"); load();
    } catch (e) { toast.error(e.message); }
  };
  const verify = async (a, i, status) => {
    try {
      await api(`/audits/${a.audit_id}/items/${i.asset_id}`, { method: "PATCH", body: JSON.stringify({ verification: status }) });
      toast.success("Audit item saved"); load();
    } catch (e) { toast.error(e.message); }
  };
  const attachPhoto = async (a, i, uploaded) => {
    try {
      await api(`/audits/${a.audit_id}/items/${i.asset_id}/photos`, { method: "POST", body: JSON.stringify(uploaded) });
      load();
    } catch (e) { toast.error(e.message); }
  };
  return (
    <>
      <PageHeader eyebrow="ACCOUNTABILITY" title="Audit cycles" description="Verify expected locations, attach evidence photos, and close audit cycles." action={<button data-testid="audit-create-button" className="primary-btn" onClick={create}><Plus size={14} /> Open cycle</button>} />
      <div className="toolbar">
        <input data-testid="audit-department-input" value={department} onChange={(e) => setDepartment(e.target.value)} placeholder="Department" />
        <input data-testid="audit-period-input" value={period} onChange={(e) => setPeriod(e.target.value)} placeholder="Period" />
      </div>
      {items.map((a) => (
        <section className="surface audit-card" key={a.audit_id}>
          <div className="section-title"><div><p className="eyebrow">{a.period} · {a.department}</p><h3>{a.audit_id}</h3></div><Status>{a.status}</Status></div>
          {a.items.slice(0, 8).map((i) => (
            <div data-testid="audit-item-row" className="audit-row" key={i.asset_id}>
              <div className="audit-row-main">
                <div><b>{i.name}</b><small>{i.tag} · expected {i.expected_location}</small></div>
                <div className="audit-actions">{["Verified", "Missing", "Damaged"].map((s) => <button data-testid={`audit-${s.toLowerCase()}-button`} className={i.verification === s ? "selected" : ""} key={s} onClick={() => verify(a, i, s)}>{s}</button>)}</div>
                <Status>{i.verification}</Status>
                <PhotoUploadButton folder={`assetflow/audits/${a.audit_id}/${i.asset_id}`} onUploaded={(u) => attachPhoto(a, i, u)} label={<><ImageIcon size={12} /> Evidence</>} testId="audit-photo-upload" />
              </div>
              {i.photos && i.photos.length > 0 && <PhotoStrip photos={i.photos} canDelete={false} />}
            </div>
          ))}
          {a.status === "Open" && (
            <button data-testid="audit-close-button" className="secondary-btn compact" style={{ marginTop: 12 }} onClick={async () => { await api(`/audits/${a.audit_id}/close`, { method: "POST" }); toast.success("Audit cycle closed"); load(); }}>Close audit cycle</button>
          )}
        </section>
      ))}
      {!items.length && <div className="empty">No audit cycles yet. Open the first one above.</div>}
    </>
  );
}

function NoDues() {
  const [items, setItems] = useState([]);
  const load = useCallback(() => api("/nodues").then(setItems).catch((e) => toast.error(e.message)), []);
  useEffect(() => { load(); }, [load]);
  const update = async (x, d) => {
    try {
      await api(`/nodues/${x.student_id}/${d.department}`, { method: "PATCH", body: JSON.stringify({ status: "Cleared", note: "Verified by department" }) });
      toast.success("No-dues status updated"); load();
    } catch (e) { toast.error(e.message); }
  };
  return (
    <>
      <PageHeader eyebrow="STUDENT CLEARANCE" title="No-dues clearance" description="Resolve department holds and issue a reliable clearance status." />
      <section className="surface table-surface">
        <div className="table-head"><span>STUDENT</span><span>ROLL NUMBER</span><span>DEPARTMENTS</span><span>OVERALL</span><span /></div>
        {items.map((x) => (
          <div data-testid="nodues-student-row" className="table-row" key={x.student_id}>
            <div><b>{x.student_name}</b><small>{x.student_id}</small></div>
            <div className="mono">{x.roll_number}</div>
            <div className="audit-actions">{x.department_statuses.map((d) => <button data-testid="nodues-clear-button" className={d.status === "Cleared" ? "selected" : ""} key={d.department} onClick={() => update(x, d)}>{d.department}: {d.status}</button>)}</div>
            <Status>{x.overall_status}</Status>
            <ChevronRight size={14} />
          </div>
        ))}
        {!items.length && <div className="empty">No students loaded.</div>}
      </section>
    </>
  );
}

function Admin() {
  const [users, setUsers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [categories, setCategories] = useState([]);
  const [dept, setDept] = useState("");
  const [category, setCategory] = useState("");
  const [tab, setTab] = useState("dept");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => Promise.all([api("/admin/users"), api("/admin/departments"), api("/admin/categories")])
    .then(([u, d, c]) => { setUsers(u); setDepartments(d); setCategories(c); })
    .catch((e) => toast.error(e.message)), []);
  useEffect(() => { load(); }, [load]);
  const add = async (path, body, resetter) => {
    try {
      await api(path, { method: "POST", body: JSON.stringify(body) });
      toast.success("Saved and logged"); resetter && resetter(""); load();
    } catch (e) { toast.error(e.message); }
  };
  const role = async (u, r) => {
    try {
      await api(`/admin/users/${u.user_id}/role`, { method: "PATCH", body: JSON.stringify({ role: r, status: "Active" }) });
      toast.success("Role updated"); load();
    } catch (e) { toast.error(e.message); }
  };
  const download = async (format) => {
    setBusy(true);
    try {
      const res = await fetch(`${API}/reports/accreditation/download?format=${format}`, { credentials: "include" });
      if (!res.ok) throw new Error("Download failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `assetflow_accreditation.${format}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success(`Downloaded ${format.toUpperCase()}`);
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  const staff = users.filter((u) => ["Employee", "HOD", "Asset Manager", "Admin"].includes(u.role));
  const students = users.filter((u) => u.role === "Student");
  return (
    <>
      <PageHeader eyebrow="ADMINISTRATION" title="Admin console" description="Manage campus structure, accounts, and accreditation evidence." action={
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button data-testid="accreditation-export-csv" className="secondary-btn compact" disabled={busy} onClick={() => download("csv")}><Download size={13} /> CSV</button>
          <button data-testid="accreditation-export-pdf" className="primary-btn compact" disabled={busy} onClick={() => download("pdf")}><FileText size={13} /> Export PDF</button>
        </div>
      } />
      <section className="surface" style={{ marginBottom: 16 }}>
        <div className="section-title"><div><p className="eyebrow">ORGANIZATION SETUP</p><h3>Configure your campus</h3></div></div>
        <div className="tabs" style={{ marginBottom: 18 }}>
          {[["dept", "Departments"], ["cat", "Categories"], ["staff", "Staff"], ["student", "Students"]].map(([k, label]) => (
            <button data-testid={`admin-tab-${k}`} key={k} className={tab === k ? "selected" : ""} onClick={() => setTab(k)}>{label}</button>
          ))}
        </div>
        {tab === "dept" && (
          <>
            <div className="inline-form" style={{ marginBottom: 14 }}>
              <input data-testid="admin-department-input" placeholder="New department" value={dept} onChange={(e) => setDept(e.target.value)} />
              <button data-testid="admin-add-department-button" className="primary-btn compact" onClick={() => add("/admin/departments", { name: dept }, setDept)}><Plus size={13} /> Add</button>
            </div>
            {departments.map((x) => <div className="simple-row" key={x.department_id}><b>{x.name}</b><small>{x.type} · {x.status}</small></div>)}
          </>
        )}
        {tab === "cat" && (
          <>
            <div className="inline-form" style={{ marginBottom: 14 }}>
              <input data-testid="admin-category-input" placeholder="New category" value={category} onChange={(e) => setCategory(e.target.value)} />
              <button data-testid="admin-add-category-button" className="primary-btn compact" onClick={() => add("/admin/categories", { name: category }, setCategory)}><Plus size={13} /> Add</button>
            </div>
            {categories.map((x) => <div className="simple-row" key={x.category_id}><b>{x.name}</b><small>{x.example_items}</small></div>)}
          </>
        )}
        {tab === "staff" && (
          <div>
            {staff.length === 0 && <div className="empty">No staff accounts yet.</div>}
            {staff.map((u) => (
              <div data-testid="admin-staff-row" className="report-row" key={u.user_id}>
                <div><b>{u.name}</b><small>{u.email} · {u.department}</small></div>
                <select data-testid="admin-role-select" value={u.role} onChange={(e) => role(u, e.target.value)}>
                  <option>Student</option><option>Employee</option><option>HOD</option><option>Asset Manager</option><option>Admin</option>
                </select>
                <Status>{u.status}</Status>
              </div>
            ))}
          </div>
        )}
        {tab === "student" && (
          <div>
            {students.length === 0 && <div className="empty">No student accounts yet.</div>}
            {students.map((u) => (
              <div data-testid="admin-student-row" className="report-row" key={u.user_id}>
                <div><b>{u.name}</b><small>{u.email} · {u.department}</small></div>
                <select data-testid="admin-role-select" value={u.role} onChange={(e) => role(u, e.target.value)}>
                  <option>Student</option><option>Employee</option><option>HOD</option><option>Asset Manager</option><option>Admin</option>
                </select>
                <Status>{u.status}</Status>
              </div>
            ))}
          </div>
        )}
      </section>
      <section className="surface">
        <div className="section-title"><div><p className="eyebrow">ROLE APPROVAL QUEUE</p><h3>Pending & recently changed</h3></div></div>
        {users.filter((x) => x.email !== "admin@assetflow.edu").map((u) => (
          <div data-testid="admin-user-row" className="report-row" key={u.user_id}>
            <div><b>{u.name}</b><small>{u.email} · {u.department}</small></div>
            <select data-testid="admin-role-select" value={u.role} onChange={(e) => role(u, e.target.value)}>
              <option>Student</option><option>Employee</option><option>HOD</option><option>Asset Manager</option><option>Admin</option>
            </select>
            <Status>{u.status}</Status>
          </div>
        ))}
      </section>
      <BrandingPanel />
    </>
  );
}

/* ============================================================
   QR Scan Page
   ============================================================ */
function ScanPage() {
  const navHook = useNavigate();
  const loc = useLocation();
  const [manualTag, setManualTag] = useState("");
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");
  const [foundAsset, setFoundAsset] = useState(null);
  const readerRef = useRef(null);
  const scannerRef = useRef(null);

  const resolveTag = useCallback(async (tag) => {
    try {
      const asset = await api(`/assets/by-tag/${encodeURIComponent(tag)}`);
      setFoundAsset(asset); setError("");
    } catch (e) { setError(e.message); setFoundAsset(null); }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(loc.search);
    const tag = params.get("tag");
    if (tag) resolveTag(tag);
  }, [loc.search, resolveTag]);

  const startScan = async () => {
    setError(""); setFoundAsset(null); setScanning(true);
    try {
      const scanner = new Html5Qrcode("qr-reader");
      scannerRef.current = scanner;
      await scanner.start({ facingMode: "environment" }, { fps: 10, qrbox: { width: 240, height: 240 } },
        async (decodedText) => {
          try { await scanner.stop(); } catch (_e) {}
          setScanning(false);
          let tag = decodedText;
          try { const u = new URL(decodedText); tag = u.searchParams.get("tag") || decodedText; } catch (_e) {}
          resolveTag(tag);
        }, () => {});
    } catch (e) {
      setError("Camera unavailable — enter tag manually below.");
      setScanning(false);
    }
  };

  const stopScan = async () => {
    if (scannerRef.current) { try { await scannerRef.current.stop(); } catch (_e) {} }
    setScanning(false);
  };

  useEffect(() => () => { if (scannerRef.current) { scannerRef.current.stop().catch(() => {}); } }, []);

  const checkAction = async (path) => {
    try {
      await api(path, { method: "POST", body: path.endsWith("/checkout") ? JSON.stringify({ holder: "Scanned check-out" }) : undefined });
      toast.success("Asset updated");
      navHook(`/inventory/${foundAsset.asset_id}`);
    } catch (e) { toast.error(e.message); }
  };

  return (
    <div className="qr-scan-page" data-testid="qr-scan-page">
      <div className="qr-scan-head">
        <button className="back-btn" onClick={() => navHook(-1)} data-testid="qr-scan-back"><ArrowLeft size={14} /> Back</button>
        <h1>Scan asset</h1>
        <div style={{ width: 60 }} />
      </div>
      <div ref={readerRef} className="qr-viewport"><div id="qr-reader" /></div>
      <div className="qr-manual">
        {!scanning ? (
          <button className="primary-btn" onClick={startScan} data-testid="qr-start-camera"><Camera size={14} /> Start camera</button>
        ) : (
          <button className="secondary-btn" onClick={stopScan} data-testid="qr-stop-camera"><X size={14} /> Stop camera</button>
        )}
        <div className="qr-hint">Point at an asset tag or paste it manually.</div>
        <form onSubmit={(e) => { e.preventDefault(); if (manualTag.trim()) resolveTag(manualTag.trim()); }} style={{ display: "flex", gap: 8 }}>
          <input data-testid="qr-manual-input" placeholder="e.g. AF-2025-1001" value={manualTag} onChange={(e) => setManualTag(e.target.value)} style={{ flex: 1, minHeight: 44, borderRadius: 6, border: "1px solid var(--hairline)", padding: "0 12px", background: "var(--elev)", color: "var(--ink)" }} />
          <button className="primary-btn" data-testid="qr-lookup-button">Look up <ArrowRight size={14} /></button>
        </form>
      </div>
      {error && <div className="qr-hint" style={{ color: "var(--error)" }} data-testid="qr-scan-error">{error}</div>}
      {foundAsset && (
        <div className="qr-result" data-testid="qr-scan-result">
          <p className="eyebrow">MATCH</p>
          <h3 style={{ margin: 0, font: "600 18px var(--font-sans)", letterSpacing: "-.5px" }}>{foundAsset.name}</h3>
          <p style={{ margin: 0, color: "var(--body)", fontSize: 13 }}>{foundAsset.location} · {foundAsset.department}</p>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
            <span className="mono muted">{foundAsset.tag}</span>
            <Status>{foundAsset.status}</Status>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
            <NavLink to={`/inventory/${foundAsset.asset_id}`} className="secondary-btn"><Eye size={13} /> Open detail</NavLink>
            {foundAsset.status === "Available" ? (
              <button className="primary-btn" data-testid="qr-checkout" onClick={() => checkAction(`/assets/${foundAsset.asset_id}/checkout`)}><ClipboardCheck size={13} /> Check out</button>
            ) : (
              <button className="primary-btn" data-testid="qr-checkin" onClick={() => checkAction(`/assets/${foundAsset.asset_id}/checkin`)}><Check size={13} /> Check in</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ============================================================
   Weekly Digest (admin only)
   ============================================================ */
function DigestPage() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api("/digest/weekly").then(setData).catch((e) => toast.error(e.message)); }, []);
  const print = () => window.print();
  const download = async (format) => {
    setBusy(true);
    try {
      const res = await fetch(`${API}/reports/accreditation/download?format=${format}`, { credentials: "include" });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = `assetflow_accreditation.${format}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  if (!data) return <div className="loading">Preparing your digest…</div>;
  const k = data.kpis;
  return (
    <>
      <PageHeader eyebrow={`WEEK OF · ${data.week_of}`} title={<>Monday <em>digest</em></>} description="A quiet Monday-morning summary of everything that needs eyes this week." action={
        <div style={{ display: "flex", gap: 8 }}>
          <button data-testid="digest-print" className="secondary-btn" onClick={print}><FileText size={13} /> Print</button>
          <button data-testid="digest-download-pdf" className="primary-btn" disabled={busy} onClick={() => download("pdf")}><Download size={13} /> Export PDF</button>
        </div>
      } />
      <div className="metric-grid">
        {[
          ["Open maintenance", k.open_maintenance, "Awaiting closure", Wrench],
          ["Resolved this week", k.resolved_this_week, "Great work", Check],
          ["Pending approvals", k.pending_approvals, "Awaiting your OK", Users],
          ["Utilization", `${k.utilization}%`, "Assets in use", BarChart3],
        ].map(([label, value, sub, Icon]) => (
          <div className="metric" data-testid={`digest-metric-${label.toLowerCase().replaceAll(" ", "-")}`} key={label}>
            <div className="metric-top"><span>{label}</span><Icon size={16} /></div>
            <strong>{value}</strong><small>{sub}</small>
          </div>
        ))}
      </div>
      <div className="dashboard-grid">
        <section className="surface">
          <div className="section-title"><div><p className="eyebrow">WORK ORDERS</p><h3>Open maintenance</h3></div><NavLink to="/maintenance" className="link-btn">Open board <ArrowRight size={13} /></NavLink></div>
          {data.open_maintenance.length === 0 ? <div className="empty">Nothing open right now.</div> : data.open_maintenance.map((m) => (
            <div className="log-row" data-testid="digest-maintenance-row" key={m.request_id}>
              <span className="activity-icon"><Wrench size={13} /></span>
              <div style={{ flex: 1 }}><b>{m.description}</b><small>{m.asset_id} · {m.raised_by} · <Status>{m.priority}</Status></small></div>
              <Status>{m.status}</Status>
            </div>
          ))}
        </section>
        <section className="surface">
          <div className="section-title"><div><p className="eyebrow">APPROVALS</p><h3>Pending accounts</h3></div><NavLink to="/admin" className="link-btn">Review <ArrowRight size={13} /></NavLink></div>
          {data.pending_users.length === 0 ? <div className="empty">No pending accounts.</div> : data.pending_users.map((u) => (
            <div className="log-row" data-testid="digest-pending-user" key={u.user_id}>
              <span className="activity-icon"><User size={13} /></span>
              <div style={{ flex: 1 }}><b>{u.name}</b><small>{u.email} · currently {u.role}</small></div>
              <Status>{u.status}</Status>
            </div>
          ))}
        </section>
      </div>
      <section className="surface" style={{ marginTop: 16 }}>
        <div className="section-title"><div><p className="eyebrow">CALENDAR</p><h3>Upcoming bookings</h3></div><NavLink to="/bookings" className="link-btn">View <ArrowRight size={13} /></NavLink></div>
        {data.upcoming_bookings.length === 0 ? <div className="empty">No confirmed bookings this week.</div> : data.upcoming_bookings.map((b) => (
          <div className="log-row" data-testid="digest-booking-row" key={b.booking_id}>
            <span className="activity-icon"><Clock3 size={13} /></span>
            <div style={{ flex: 1 }}><b>{b.resource_id}</b><small>{b.date} {b.start_time}–{b.end_time} · {b.requested_by}</small></div>
            <Status>{b.status}</Status>
          </div>
        ))}
      </section>
      <section className="surface" style={{ marginTop: 16 }}>
        <div className="section-title"><div><p className="eyebrow">AUDITS</p><h3>Open cycles</h3></div></div>
        {data.open_audits.length === 0 ? <div className="empty">No open audits.</div> : data.open_audits.map((a) => (
          <div className="log-row" data-testid="digest-audit-row" key={a.audit_id}>
            <span className="activity-icon"><ClipboardCheck size={13} /></span>
            <div style={{ flex: 1 }}><b>{a.department}</b><small>{a.period} · {a.pending_items} items pending verification</small></div>
          </div>
        ))}
      </section>
    </>
  );
}

/* ============================================================
   Branding editor (admin only)
   ============================================================ */
function BrandingPanel() {
  const [brand, setBrand] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api("/admin/branding").then(setBrand); }, []);
  if (!brand) return <div className="loading">Loading branding…</div>;
  const set = (k, v) => setBrand((b) => ({ ...b, [k]: v }));
  const save = async () => {
    setBusy(true);
    try {
      const saved = await api("/admin/branding", { method: "PUT", body: JSON.stringify(brand) });
      setBrand(saved); toast.success("Branding saved");
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  const uploadLogo = async (uploaded) => set("logo_url", uploaded.secure_url);
  return (
    <section className="surface" data-testid="branding-panel" style={{ marginTop: 16 }}>
      <div className="section-title"><div><p className="eyebrow">NAAC / NBA COVER SHEET</p><h3>Report branding</h3></div>
        <button data-testid="branding-save" className="primary-btn compact" disabled={busy} onClick={save}><Check size={13} /> {busy ? "Saving…" : "Save"}</button>
      </div>
      <div className="branding-grid">
        <label>Institution name<input data-testid="branding-name" value={brand.institution_name} onChange={(e) => set("institution_name", e.target.value)} /></label>
        <label>Tagline<input data-testid="branding-tagline" value={brand.tagline} onChange={(e) => set("tagline", e.target.value)} /></label>
        <label>Accreditation body<input data-testid="branding-body" value={brand.accreditation_body} onChange={(e) => set("accreditation_body", e.target.value)} /></label>
        <label>Accent colour<input data-testid="branding-color" type="color" value={brand.accent_color} onChange={(e) => set("accent_color", e.target.value)} /></label>
        <label style={{ gridColumn: "1 / -1" }}>Footer<textarea data-testid="branding-footer" value={brand.footer} onChange={(e) => set("footer", e.target.value)} rows={2} /></label>
        <div style={{ gridColumn: "1 / -1", display: "flex", gap: 16, alignItems: "center" }}>
          {brand.logo_url ? <img src={brand.logo_url} alt="logo" style={{ width: 64, height: 64, objectFit: "contain", borderRadius: 8, border: "1px solid var(--hairline)", background: "var(--elev)" }} /> : <div style={{ width: 64, height: 64, borderRadius: 8, background: "var(--hairline-soft)", border: "1px dashed var(--hairline)", display: "grid", placeItems: "center", color: "var(--mute)" }}><ImageIcon size={20} /></div>}
          <div style={{ display: "grid", gap: 4 }}>
            <PhotoUploadButton folder="assetflow/branding/logo" onUploaded={uploadLogo} label={<><Upload size={12} /> Upload logo</>} testId="branding-logo-upload" />
            {brand.logo_url && <button data-testid="branding-logo-clear" className="advance-btn" style={{ width: "auto", marginTop: 0, padding: "6px 10px" }} onClick={() => set("logo_url", "")}><X size={12} /> Remove logo</button>}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ============================================================
   Router
   ============================================================ */
function ProtectedApp() {
  const loc = useLocation();
  if (loc.hash.includes("session_id=")) return <AuthCallback />;
  return (
    <AuthGate>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/inventory" element={<Inventory />} />
        <Route path="/inventory/:asset_id" element={<AssetDetail />} />
        <Route path="/bookings" element={<Bookings />} />
        <Route path="/maintenance" element={<Maintenance />} />
        <Route path="/audits" element={<Audits />} />
        <Route path="/nodues" element={<NoDues />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/activity" element={<ActivityPage />} />
        <Route path="/digest" element={<DigestPage />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/scan" element={<ScanPage />} />
        <Route path="*" element={<Dashboard />} />
      </Routes>
    </AuthGate>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Toaster position="bottom-right" theme="system" />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<ProtectedApp />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

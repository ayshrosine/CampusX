import { useCallback, useEffect, useRef, useState } from "react";
import { BrowserRouter, Routes, Route, NavLink, useLocation, useNavigate, useParams } from "react-router-dom";
import { Activity, Archive, ArrowLeft, ArrowRight, BarChart3, Bell, Box, Calendar, Camera, Check, CheckCircle2, ChevronDown, ChevronRight, ClipboardCheck, Clock3, Download, Eye, FileText, Filter, GripVertical, Hammer, Image as ImageIcon, Layers, LayoutDashboard, LogOut, MapPin, Menu, MoreHorizontal, Moon, Package, Pencil, Plus, QrCode, RefreshCw, Search, Settings2, Shield, SlidersHorizontal, Sparkles, Sun, Trash2, Upload, User, Users, Wrench, X, Zap } from "lucide-react";
import { Toaster, toast } from "sonner";
import { QRCodeSVG } from "qrcode.react";
import { Html5Qrcode } from "html5-qrcode";
import { DragDropContext, Droppable, Draggable } from "@hello-pangea/dnd";
import OrbitTrails from "@/components/OrbitTrails";
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

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const b = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(b);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

async function ensurePushSubscription() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) throw new Error("Push not supported on this browser");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") throw new Error("Notifications permission was denied");
  const reg = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;
  const existing = await reg.pushManager.getSubscription();
  if (existing) return existing;
  const { key } = await api("/push/public-key");
  if (!key) throw new Error("Push server key not configured");
  return reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(key) });
}

const ROLE_PERMISSIONS = {
  Admin: new Set(["admin", "asset_write", "maintenance_write", "booking", "audit", "nodues", "reports"]),
  "Asset Manager": new Set(["asset_write", "maintenance_write", "booking", "audit", "reports"]),
  HOD: new Set(["asset_write", "maintenance_write", "booking", "reports"]),
  Employee: new Set(["maintenance_write", "booking", "reports"]),
  Student: new Set(["booking", "maintenance_write"]),
};

const fmt = (v) => v ? new Date(v).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";
const initials = (n = "") => n.split(" ").map((x) => x[0]).filter(Boolean).join("").slice(0, 2).toUpperCase();
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
function AuthGate({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navHook = useNavigate();
  useEffect(() => {
    api("/auth/me").then(setUser).catch(() => setUser(false)).finally(() => setLoading(false));
  }, []);
  if (loading) return <div className="auth-loading">Loading AssetFlow…</div>;
  if (!user) { navHook("/login", { replace: true }); return null; }
  return (
    <Shell user={user} onUserUpdate={setUser} onLogout={() => api("/auth/logout", { method: "POST" }).then(() => navHook("/login"))}>
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
  const googleButtonRef = useRef(null);
  
  useEffect(() => { document.documentElement.classList.toggle("dark", dark); localStorage.theme = dark ? "dark" : "light"; }, [dark]);

  const submit = async (e) => {
    e.preventDefault(); setBusy(true);
    try {
      await api(mode === "login" ? "/auth/login" : "/auth/signup", { method: "POST", body: JSON.stringify(form) });
      navHook("/dashboard");
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };

  const handleGoogleCredential = useCallback(async (response) => {
    try {
      const idToken = response.credential;
      await api("/auth/session", { 
        method: "POST", 
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential: idToken })
      });
      navHook("/dashboard");
    } catch (err) { 
      toast.error(err.message); 
    }
  }, [navHook]);

  useEffect(() => {
    if (window.google && googleButtonRef.current) {
      window.google.accounts.id.initialize({
        client_id: process.env.REACT_APP_GOOGLE_CLIENT_ID,
        callback: handleGoogleCredential,
        auto_select: false,
        itp_support: true,
        use_fedcm_for_button: false,
      });

      window.google.accounts.id.renderButton(
        googleButtonRef.current,
        {
          theme: "outline",
          size: "large",
          text: "signin_with",
          shape: "rectangular",
          logo_alignment: "left",
          width: "100%"
        }
      );
    }
  }, [handleGoogleCredential]);

  return (
    <main className="auth-page auth-page--orbit">
      <OrbitTrails colors={["#8f7bff", "#5b6cff", "#c96af2"]} background="#0f1013" speed={1.0} trails={80} />
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
          <div ref={googleButtonRef} data-testid="google-signin-button"></div>
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
  const [pushOn, setPushOn] = useState(false);
  const navHook = useNavigate();
  useEffect(() => {
    if (!open) return;
    api("/notifications").then(setData).catch((e) => toast.error(e.message));
    api("/notifications/mark-all-read", { method: "POST" }).catch(() => {});
    if ("serviceWorker" in navigator && "PushManager" in window) {
      navigator.serviceWorker.getRegistration().then((reg) => reg?.pushManager?.getSubscription().then((s) => setPushOn(!!s)));
    }
  }, [open]);
  const enablePush = async () => {
    try {
      const sub = await ensurePushSubscription();
      const json = sub.toJSON();
      await api("/push/subscribe", { method: "POST", body: JSON.stringify({ endpoint: json.endpoint, keys: json.keys }) });
      setPushOn(true);
      toast.success("Browser push enabled");
    } catch (e) { toast.error(e.message); }
  };
  if (!open) return null;
  const kindIcons = { maintenance: <Wrench size={14} />, booking: <Clock3 size={14} />, approval: <Users size={14} />, audit: <ClipboardCheck size={14} /> };
  return (
    <>
      <div className="scrim" style={{ display: "block", background: "transparent" }} onClick={onClose} />
      <div className="notif-drawer" data-testid="notifications-drawer">
        <div className="notif-head">
          <h3>Notifications</h3>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            {!pushOn && ("Notification" in window) && (
              <button data-testid="enable-push-button" className="advance-btn" style={{ width: "auto", padding: "6px 10px", marginTop: 0 }} onClick={enablePush}><Bell size={12} /> Enable push</button>
            )}
            <button className="icon-btn" style={{ width: 28, height: 28 }} onClick={onClose} aria-label="Close notifications"><X size={14} /></button>
          </div>
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
          <small style={{ color: "var(--mute)", fontFamily: "var(--font-mono)", fontSize: 11 }}>{data.items.length} items · push {pushOn ? "on" : "off"}</small>
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
function GlobalSearch({ onClose }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState({ assets: [], users: [], bookings: [], maintenance: [] });
  const navigate = useNavigate();
  useEffect(() => {
    const id = setTimeout(() => {
      if (q.trim().length >= 1) api(`/search?q=${encodeURIComponent(q.trim())}`).then(setRes).catch(() => {});
      else setRes({ assets: [], users: [], bookings: [], maintenance: [] });
    }, 200);
    return () => clearTimeout(id);
  }, [q]);
  const pages = q ? nav.filter((n) => n.label.toLowerCase().includes(q.toLowerCase())) : [];
  const go = (to) => { navigate(to); onClose(); };
  const firstTarget = () => {
    if (res.assets[0]) return `/inventory/${res.assets[0].asset_id}`;
    if (pages[0]) return pages[0].to;
    if (res.maintenance[0]) return "/maintenance";
    if (res.bookings[0]) return "/bookings";
    if (res.users[0]) return "/admin";
    return null;
  };
  const total = pages.length + res.assets.length + res.maintenance.length + res.bookings.length + res.users.length;
  return (
    <div className="modal-backdrop search-backdrop" onClick={onClose} data-testid="global-search-overlay">
      <div className="search-panel" onClick={(e) => e.stopPropagation()}>
        <div className="search-input-row">
          <Search size={16} />
          <input autoFocus data-testid="global-search-input" placeholder="Search assets, users, bookings, tickets, pages…" value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { const t = firstTarget(); if (t) go(t); } if (e.key === "Escape") onClose(); }} />
          <button className="icon-btn" onClick={onClose} aria-label="Close"><X size={16} /></button>
        </div>
        <div className="search-results">
          {pages.length > 0 && <div className="search-group">Pages</div>}
          {pages.map((p) => <button key={p.to} className="search-item" data-testid="search-result-page" onClick={() => go(p.to)}><p.icon size={15} /> <span><b>{p.label}</b></span></button>)}
          {res.assets.length > 0 && <div className="search-group">Assets</div>}
          {res.assets.map((a) => <button key={a.asset_id} className="search-item" data-testid="search-result-asset" onClick={() => go(`/inventory/${a.asset_id}`)}><Package size={15} /> <span><b>{a.name}</b><small>{a.tag} · {a.location}</small></span></button>)}
          {res.maintenance.length > 0 && <div className="search-group">Maintenance</div>}
          {res.maintenance.map((m) => <button key={m.request_id} className="search-item" data-testid="search-result-maintenance" onClick={() => go("/maintenance")}><Wrench size={15} /> <span><b>{m.description}</b><small>{m.asset_id} · {m.priority} · {m.status}</small></span></button>)}
          {res.bookings.length > 0 && <div className="search-group">Bookings</div>}
          {res.bookings.map((b) => <button key={b.booking_id} className="search-item" data-testid="search-result-booking" onClick={() => go("/bookings")}><Clock3 size={15} /> <span><b>{b.event_title || b.purpose}</b><small>{b.resource_name || b.resource_id} · {b.date}</small></span></button>)}
          {res.users.length > 0 && <div className="search-group">Users</div>}
          {res.users.map((u) => <button key={u.user_id} className="search-item" data-testid="search-result-user" onClick={() => go("/admin")}><User size={15} /> <span><b>{u.name}</b><small>{u.email} · {u.role}</small></span></button>)}
          {q && total === 0 && <div className="search-empty">No matches for &ldquo;{q}&rdquo;</div>}
          {!q && <div className="search-empty">Search assets, users, bookings, tickets and pages…</div>}
        </div>
      </div>
    </div>
  );
}

function ProfileMenu({ user, onEdit, onLogout }) {
  return (
    <div className="profile-menu" data-testid="profile-menu" onClick={(e) => e.stopPropagation()}>
      <div className="profile-head">
        <span className="avatar-lg">{initials(user.name)}</span>
        <div className="profile-head-info"><b>{user.name}</b><small>{user.email}</small><span className="role-tag">{user.role}</span></div>
      </div>
      <button className="profile-item" data-testid="profile-edit-button" onClick={onEdit}><User size={15} /> Edit profile</button>
      <button className="profile-item danger" data-testid="profile-logout-button" onClick={onLogout}><LogOut size={15} /> Log out</button>
    </div>
  );
}

function ProfileModal({ user, onClose, onSaved }) {
  const [form, setForm] = useState({ name: user.name || "", department: user.department || "", phone: user.phone || "" });
  const [busy, setBusy] = useState(false);
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { const u = await api("/auth/profile", { method: "PATCH", body: JSON.stringify(form) }); toast.success("Profile updated"); onSaved(u); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} data-testid="profile-modal">
        <div className="modal-title"><div><p className="eyebrow">MY PROFILE</p><h2>Edit profile</h2></div><button className="icon-btn" onClick={onClose} aria-label="Close" data-testid="profile-modal-close"><X size={16} /></button></div>
        <form onSubmit={save}>
          <div className="nb-field"><label>Full name</label><input data-testid="profile-name-input" className="nb-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required minLength={2} /></div>
          <div className="nb-field"><label>Department</label><input data-testid="profile-department-input" className="nb-input" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} placeholder="e.g. Computer Science" /></div>
          <div className="nb-field"><label>Phone</label><input data-testid="profile-phone-input" className="nb-input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="Contact number" /></div>
          <div className="nb-field"><label>Email (read-only)</label><input className="nb-input" value={user.email} disabled /></div>
          <div className="nb-field"><label>Role (set by admin)</label><input className="nb-input" value={user.role} disabled /></div>
          <button className="primary-btn nb-confirm" data-testid="profile-save-button" disabled={busy} type="submit">{busy ? "Saving…" : "Save changes"}</button>
        </form>
      </div>
    </div>
  );
}

function Shell({ user, onLogout, onUserUpdate, children }) {
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
  const [searchOpen, setSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setSearchOpen(true); }
      if (e.key === "Escape") setSearchOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
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
            <button data-testid="global-search-button" className="search-trigger" onClick={() => setSearchOpen(true)}><Search size={13} /> Search <kbd>⌘K</kbd></button>
            <ThemeToggleButton dark={dark} setDark={setDark} className="icon-btn" />
            <button data-testid="notifications-button" className="icon-btn" onClick={() => setNotifOpen(true)} aria-label="Notifications">
              <Bell size={16} />
              {unread > 0 && <span className="badge" data-testid="notifications-badge">{unread}</span>}
            </button>
            <div className="user-menu">
              <button data-testid="profile-button" className="user-chip" onClick={(e) => { e.stopPropagation(); setProfileOpen((o) => !o); }}>
                <span>{initials(user.name)}</span><div><b>{user.name}</b><small>{user.role}</small></div>
              </button>
              {profileOpen && (<>
                <div className="menu-scrim" onClick={() => setProfileOpen(false)} />
                <ProfileMenu user={user} onEdit={() => { setEditOpen(true); setProfileOpen(false); }} onLogout={onLogout} />
              </>)}
            </div>
          </div>
        </header>
        <main className="page-content">{children}</main>
      </section>
      <Notifications user={user} open={notifOpen} onClose={() => setNotifOpen(false)} />
      {previewOpen && <RolePreviewModal onClose={() => setPreviewOpen(false)} />}
      {searchOpen && <GlobalSearch onClose={() => setSearchOpen(false)} />}
      {editOpen && <ProfileModal user={user} onClose={() => setEditOpen(false)} onSaved={(u) => { onUserUpdate && onUserUpdate(u); setEditOpen(false); }} />}
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
  const [newAsset, setNewAsset] = useState({ name: "", category: "IT Equipment", location: "", department: "Computer Science", status: "Available", serial: "", bookable: false, supplier: "", purchase_cost: "", purchase_date: "", warranty_end: "", amc_provider: "", notes: "" });
  const load = useCallback(() => api(`/assets?search=${encodeURIComponent(search)}&status=${status}`).then(setAssets).catch((e) => toast.error(e.message)), [search, status]);
  useEffect(() => { load(); }, [load]);
  const resetAsset = () => setNewAsset({ name: "", category: "IT Equipment", location: "", department: "Computer Science", status: "Available", serial: "", bookable: false, supplier: "", purchase_cost: "", purchase_date: "", warranty_end: "", amc_provider: "", notes: "" });
  const save = async (e) => {
    e.preventDefault();
    try {
      await api("/assets", { method: "POST", body: JSON.stringify({ ...newAsset, purchase_cost: Number(newAsset.purchase_cost) || 0 }) });
      toast.success("Asset registered and logged");
      setShow(false); resetAsset(); load();
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
          <form className="modal modal-wide" onClick={(e) => e.stopPropagation()} onSubmit={save}>
            <div className="modal-title">
              <div><p className="eyebrow">NEW RECORD</p><h2>Register an asset</h2></div>
              <button data-testid="close-asset-modal-button" type="button" className="icon-btn" onClick={() => setShow(false)}><X size={14} /></button>
            </div>
            <div className="nb-field"><label>Asset name</label><input data-testid="new-asset-name-input" className="nb-input" placeholder="e.g. Epson Projector EB-X06" value={newAsset.name} onChange={(e) => setNewAsset({ ...newAsset, name: e.target.value })} required /></div>
            <div className="nb-row">
              <div className="nb-field"><label>Category</label>
                <select data-testid="new-asset-category-select" className="nb-input" value={newAsset.category} onChange={(e) => setNewAsset({ ...newAsset, category: e.target.value })}>
                  <option>IT Equipment</option><option>Lab Equipment</option><option>Workshop Machinery</option><option>Media Equipment</option><option>Room</option><option>Vehicle</option><option>Sports Gear</option>
                </select>
              </div>
              <div className="nb-field"><label>Status</label>
                <select data-testid="new-asset-status-select" className="nb-input" value={newAsset.status} onChange={(e) => setNewAsset({ ...newAsset, status: e.target.value })}>
                  <option>Available</option><option>Allocated</option><option>Under Maintenance</option>
                </select>
              </div>
            </div>
            <div className="nb-row">
              <div className="nb-field"><label>Location</label><input data-testid="new-asset-location-input" className="nb-input" placeholder="e.g. Seminar Hall A" value={newAsset.location} onChange={(e) => setNewAsset({ ...newAsset, location: e.target.value })} required /></div>
              <div className="nb-field"><label>Department</label><input data-testid="new-asset-department-input" className="nb-input" placeholder="e.g. Computer Science" value={newAsset.department} onChange={(e) => setNewAsset({ ...newAsset, department: e.target.value })} required /></div>
            </div>
            <div className="nb-row">
              <div className="nb-field"><label>Serial number</label><input data-testid="new-asset-serial-input" className="nb-input" placeholder="SN-XXXX (optional)" value={newAsset.serial} onChange={(e) => setNewAsset({ ...newAsset, serial: e.target.value })} /></div>
              <div className="nb-field"><label>Supplier / vendor</label><input data-testid="new-asset-supplier-input" className="nb-input" placeholder="Who supplied it" value={newAsset.supplier} onChange={(e) => setNewAsset({ ...newAsset, supplier: e.target.value })} /></div>
            </div>
            <div className="nb-row">
              <div className="nb-field"><label>Purchase cost (₹)</label><input data-testid="new-asset-cost-input" className="nb-input" type="number" min="0" step="0.01" placeholder="0.00" value={newAsset.purchase_cost} onChange={(e) => setNewAsset({ ...newAsset, purchase_cost: e.target.value })} /></div>
              <div className="nb-field"><label>Purchase date</label><input data-testid="new-asset-purchase-date-input" className="nb-input" type="date" value={newAsset.purchase_date} onChange={(e) => setNewAsset({ ...newAsset, purchase_date: e.target.value })} /></div>
            </div>
            {newAsset.category !== "Sports Gear" && newAsset.category !== "Room" && (
              <div className="nb-row">
                <div className="nb-field"><label>Warranty end date</label><input data-testid="new-asset-warranty-input" className="nb-input" type="date" value={newAsset.warranty_end} onChange={(e) => setNewAsset({ ...newAsset, warranty_end: e.target.value })} /></div>
                <div className="nb-field"><label>AMC provider</label><input data-testid="new-asset-amc-input" className="nb-input" placeholder="Annual maintenance contract" value={newAsset.amc_provider} onChange={(e) => setNewAsset({ ...newAsset, amc_provider: e.target.value })} /></div>
              </div>
            )}
            <div className="nb-field"><label>Notes</label><textarea data-testid="new-asset-notes-input" className="nb-textarea" placeholder="Any extra details…" value={newAsset.notes} onChange={(e) => setNewAsset({ ...newAsset, notes: e.target.value })} /></div>
            <label className="ac-checkline" style={{ marginBottom: 12 }}><input type="checkbox" data-testid="new-asset-bookable-checkbox" checked={newAsset.bookable} onChange={(e) => setNewAsset({ ...newAsset, bookable: e.target.checked })} /> This asset is bookable (rooms, projectors, vehicles, laptops)</label>
            <button data-testid="register-asset-submit-button" className="primary-btn nb-confirm">Register asset <Check size={13} /></button>
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
  const [assets, setAssets] = useState([]);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ asset_id: "", description: "", priority: "Medium", category: "", location: "", reporter_contact: "" });
  const load = useCallback(() => api("/maintenance").then(setItems), []);
  useEffect(() => { load(); api("/assets").then(setAssets).catch(() => {}); }, [load]);
  const pickAsset = (id) => {
    const a = assets.find((x) => x.asset_id === id);
    setForm((f) => ({ ...f, asset_id: id, category: a?.category || f.category, location: a?.location || f.location }));
  };
  const save = async (e) => {
    e.preventDefault();
    if (!form.asset_id) { toast.error("Please choose an asset"); return; }
    try {
      await api("/maintenance", { method: "POST", body: JSON.stringify(form) });
      toast.success("Request raised and logged"); setShow(false);
      setForm({ asset_id: "", description: "", priority: "Medium", category: "", location: "", reporter_contact: "" });
      load();
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
            <div className="nb-field"><label>Asset</label>
              <select data-testid="maintenance-asset-select" className="nb-input" value={form.asset_id} onChange={(e) => pickAsset(e.target.value)} required>
                <option value="">Select an asset…</option>
                {assets.map((a) => <option key={a.asset_id} value={a.asset_id}>{a.tag} · {a.name}</option>)}
              </select>
            </div>
            <div className="nb-row">
              <div className="nb-field"><label>Severity</label>
                <select data-testid="maintenance-priority-select" className="nb-input" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                  <option>Low</option><option>Medium</option><option>High</option>
                </select>
              </div>
              <div className="nb-field"><label>Category</label><input data-testid="maintenance-category-input" className="nb-input" placeholder="e.g. Electrical" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></div>
            </div>
            <div className="nb-field"><label>Location</label><input data-testid="maintenance-location-input" className="nb-input" placeholder="Where is the asset?" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></div>
            <div className="nb-field"><label>Reporter contact (phone / email)</label><input data-testid="maintenance-contact-input" className="nb-input" placeholder="Who to reach about this issue" value={form.reporter_contact} onChange={(e) => setForm({ ...form, reporter_contact: e.target.value })} /></div>
            <div className="nb-field"><label>Description</label><textarea data-testid="maintenance-description-input" className="nb-textarea" placeholder="What needs attention?" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required /></div>
            <button data-testid="maintenance-submit-button" className="primary-btn nb-confirm">Raise request <Wrench size={13} /></button>
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

/* ============================================================
   Reports & Intelligence — Granular Downloads & Report Builder
   ============================================================ */

function ReportPreviewTable({ headers = [], rows = [], total = 0, loading = false, title = "Report Preview", emptyMessage = "No matching records found" }) {
  if (loading) {
    return (
      <div className="report-preview-box">
        <div className="report-preview-header">
          <h4><Layers size={15} /> {title}</h4>
          <span className="report-count-indicator">Loading live data…</span>
        </div>
        <div className="report-table-empty"><RefreshCw size={18} className="animate-spin" style={{ display: "inline-block", marginRight: 8 }} /> Loading records…</div>
      </div>
    );
  }

  const renderCell = (cell, colIndex) => {
    if (cell === null || cell === undefined || cell === "") return <span style={{ color: "var(--mute)" }}>—</span>;
    const str = String(cell);
    const low = str.toLowerCase();
    
    // Status pills
    if (["available", "resolved", "cleared", "active", "verified", "confirmed"].includes(low)) {
      return <span className={`status status-${low}`}><i></i>{str}</span>;
    }
    if (["under maintenance", "high", "missing", "damaged", "rejected"].includes(low)) {
      return <span className="status status-under-maintenance"><i></i>{str}</span>;
    }
    if (["allocated", "in progress", "pending", "open", "medium", "low"].includes(low)) {
      const cls = low === "allocated" ? "status-allocated" : "status-pending";
      return <span className={`status ${cls}`}><i></i>{str}</span>;
    }
    // Tag formatting
    if (str.startsWith("AF-") || str.startsWith("SN-") || str.startsWith("MNT-") || str.startsWith("tmpl_")) {
      return <span className="mono" style={{ fontWeight: 600 }}>{str}</span>;
    }
    return str;
  };

  return (
    <div className="report-preview-box" data-testid="report-preview-box">
      <div className="report-preview-header">
        <h4><Layers size={15} /> {title}</h4>
        <span className="report-count-indicator">
          Showing <b>{rows.length}</b> {total ? <>of <b>{total}</b> records</> : "records"} · {headers.length} columns
        </span>
      </div>
      <div className="report-table-scroll">
        <table className="report-data-table" data-testid="report-preview-table">
          <thead>
            <tr>
              {headers.map((h, i) => (
                <th key={i}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={Math.max(1, headers.length)} className="report-table-empty">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row, rIdx) => (
                <tr key={rIdx} data-testid="report-preview-row">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx}>{renderCell(cell, cIdx)}</td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReportTemplateBuilderModal({ template, onClose, onSaved }) {
  const isEdit = !!template;
  const [sources, setSources] = useState([]);
  const [source, setSource] = useState(template?.data_source || "assets");
  const [schema, setSchema] = useState(null);
  const [name, setName] = useState(template?.name || "");
  const [description, setDescription] = useState(template?.description || "");
  const [columns, setColumns] = useState(template?.columns || []);
  const [filters, setFilters] = useState(template?.filters || {});
  const [sortBy, setSortBy] = useState(template?.sort_by || "");
  const [sortOrder, setSortOrder] = useState(template?.sort_order || "asc");
  const [roles, setRoles] = useState(template?.access_roles || ["Admin", "Asset Manager", "HOD"]);
  const [saving, setSaving] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [previewing, setPreviewing] = useState(false);

  // Load available data sources
  useEffect(() => {
    api("/reports/templates/sources").then(setSources).catch(() => {
      setSources([
        { key: "assets", label: "Assets & Equipment" },
        { key: "maintenance", label: "Maintenance & Work Orders" },
        { key: "bookings", label: "Resource Bookings" },
        { key: "users", label: "Users & Staff Roster" },
        { key: "activity", label: "Activity & Audit Events" },
        { key: "audits", label: "Audit Cycles" },
        { key: "nodues", label: "No-Dues Clearance" }
      ]);
    });
  }, []);

  // Load schema whenever data source changes
  useEffect(() => {
    if (!source) return;
    api(`/reports/templates/schema/${source}`).then((sc) => {
      setSchema(sc);
      if (!isEdit || source !== template?.data_source) {
        setColumns(sc.columns ? sc.columns.slice(0, 6).map((c) => c.key) : []);
        setFilters({});
        setSortBy(sc.columns?.[0]?.key || "");
      }
    }).catch((e) => toast.error(e.message));
  }, [source]);

  const toggleColumn = (colKey) => {
    if (columns.includes(colKey)) {
      if (columns.length === 1) { toast.error("Report must have at least one column"); return; }
      setColumns(columns.filter((c) => c !== colKey));
    } else {
      setColumns([...columns, colKey]);
    }
  };

  const selectAllColumns = () => {
    if (schema?.columns) setColumns(schema.columns.map((c) => c.key));
  };

  const clearAllColumns = () => {
    if (schema?.columns?.[0]) setColumns([schema.columns[0].key]);
  };

  const toggleRole = (r) => {
    if (roles.includes(r)) {
      if (roles.length === 1) { toast.error("Select at least one role"); return; }
      setRoles(roles.filter((x) => x !== r));
    } else {
      setRoles([...roles, r]);
    }
  };

  const handlePreview = async () => {
    setPreviewing(true);
    try {
      // Create a temporary preview query or preview endpoint
      const res = await api(`/reports/templates`, {
        method: "POST",
        body: JSON.stringify({
          name: name.trim() || "Preview Report",
          description: description.trim(),
          data_source: source,
          columns,
          filters,
          sort_by: sortBy,
          sort_order: sortOrder,
          access_roles: roles
        })
      });
      const prev = await api(`/reports/templates/${res.template_id}/preview`);
      setPreviewData(prev);
      // clean up temporary template
      await api(`/reports/templates/${res.template_id}`, { method: "DELETE" }).catch(() => {});
    } catch (e) {
      toast.error(`Preview error: ${e.message}`);
    } finally {
      setPreviewing(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!name.trim()) { toast.error("Please enter a report name"); return; }
    if (columns.length === 0) { toast.error("Select at least one column"); return; }
    setSaving(true);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim(),
        data_source: source,
        columns,
        filters,
        sort_by: sortBy,
        sort_order: sortOrder,
        access_roles: roles
      };
      let res;
      if (isEdit) {
        res = await api(`/reports/templates/${template.template_id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast.success("Template updated successfully");
      } else {
        res = await api(`/reports/templates`, { method: "POST", body: JSON.stringify(payload) });
        toast.success("Template created successfully");
      }
      onSaved(res);
      onClose();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose} data-testid="template-builder-overlay">
      <div className="builder-modal" onClick={(e) => e.stopPropagation()} data-testid="template-builder-modal">
        <div className="modal-title">
          <div>
            <p className="eyebrow">ADMIN REPORT BUILDER</p>
            <h2>{isEdit ? "Edit Report Template" : "Build Custom Report Template"}</h2>
            <p className="muted" style={{ margin: "4px 0 0" }}>Configure data source, pick columns, and define audience permissions.</p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close" data-testid="template-builder-close"><X size={16} /></button>
        </div>

        <form onSubmit={handleSave} style={{ display: "grid", gap: 16 }}>
          <div className="builder-section">
            <h5>Basic Information</h5>
            <div style={{ display: "grid", gap: 10 }}>
              <div className="report-filter-item">
                <label>Template Name *</label>
                <input
                  data-testid="template-name-input"
                  placeholder="e.g. CS Lab Equipment Status"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div className="report-filter-item">
                <label>Description / Purpose</label>
                <input
                  data-testid="template-desc-input"
                  placeholder="e.g. All lab machinery in CS dept with current status and holder"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div className="report-filter-item">
                <label>Data Source (MongoDB Collection)</label>
                <select
                  data-testid="template-source-select"
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  disabled={isEdit}
                >
                  {sources.map((s) => (
                    <option key={s.key} value={s.key}>{s.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="builder-section">
            <h5>
              <span>Select Columns ({columns.length} chosen)</span>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" className="link-btn" onClick={selectAllColumns} style={{ fontSize: 11 }}>Select all</button>
                <button type="button" className="link-btn" onClick={clearAllColumns} style={{ fontSize: 11 }}>Reset</button>
              </div>
            </h5>
            <div className="columns-checkbox-grid" data-testid="template-columns-grid">
              {(schema?.columns || []).map((col) => {
                const checked = columns.includes(col.key);
                return (
                  <label key={col.key} className="col-check-label" data-testid={`col-check-${col.key}`}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleColumn(col.key)}
                    />
                    <span>{col.label}</span>
                  </label>
                );
              })}
            </div>
          </div>

          {(schema?.filterable_fields || []).length > 0 && (
            <div className="builder-section">
              <h5>Preset Filters (Optional)</h5>
              <div className="filter-builder-grid">
                {schema.filterable_fields.map((f) => (
                  <div key={f.key} className="report-filter-item">
                    <label>{f.label}</label>
                    <input
                      placeholder="Any (or enter value)"
                      value={filters[f.key] || ""}
                      onChange={(e) => setFilters({ ...filters, [f.key]: e.target.value })}
                      data-testid={`filter-input-${f.key}`}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="builder-section">
            <h5>Sorting</h5>
            <div className="sort-builder-row">
              <div className="report-filter-item" style={{ flex: 2 }}>
                <label>Sort By Field</label>
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} data-testid="sort-by-select">
                  <option value="">Default (Registered Date)</option>
                  {(schema?.columns || []).map((c) => (
                    <option key={c.key} value={c.key}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div className="report-filter-item" style={{ flex: 1 }}>
                <label>Order</label>
                <select value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} data-testid="sort-order-select">
                  <option value="asc">Ascending (A–Z)</option>
                  <option value="desc">Descending (Z–A)</option>
                </select>
              </div>
            </div>
          </div>

          <div className="builder-section">
            <h5>Audience & Access Roles</h5>
            <div className="roles-check-row">
              {["Admin", "Asset Manager", "HOD", "Employee", "Student", "All roles"].map((r) => (
                <label key={r} className="col-check-label" data-testid={`role-check-${r.replace(" ", "-")}`}>
                  <input
                    type="checkbox"
                    checked={roles.includes(r)}
                    onChange={() => toggleRole(r)}
                  />
                  <span>{r}</span>
                </label>
              ))}
            </div>
          </div>

          {previewData && (
            <div className="builder-section">
              <h5>Live Data Preview ({previewData.total} matches)</h5>
              <ReportPreviewTable
                headers={previewData.headers}
                rows={previewData.preview_rows}
                total={previewData.total}
                title="Previewing First 20 Rows"
              />
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: 14, borderTop: "1px solid var(--hairline)" }}>
            <button
              type="button"
              className="secondary-btn"
              disabled={previewing}
              onClick={handlePreview}
              data-testid="template-builder-preview-btn"
            >
              <Eye size={13} /> {previewing ? "Previewing…" : "Preview Live Data"}
            </button>
            <div style={{ display: "flex", gap: 10 }}>
              <button type="button" className="secondary-btn" onClick={onClose}>Cancel</button>
              <button
                type="submit"
                className="primary-btn"
                disabled={saving}
                data-testid="template-builder-save-btn"
              >
                {saving ? "Saving…" : isEdit ? "Update Template" : "Save & Publish Template"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

function Reports() {
  const [currentUser, setCurrentUser] = useState(null);
  const [activeTab, setActiveTab] = useState("department");
  const [metadata, setMetadata] = useState({ departments: [], categories: [], statuses: [] });
  const [usersList, setUsersList] = useState([]);
  const [overviewData, setOverviewData] = useState(null);
  const [busy, setBusy] = useState(false);

  // Tab 1: Department Reports State
  const [selectedDept, setSelectedDept] = useState("Computer Science");
  const [deptSubreport, setDeptSubreport] = useState("assets");
  const [deptData, setDeptData] = useState(null);
  const [deptLoading, setDeptLoading] = useState(false);

  // Tab 2: By Status State
  const [selectedStatus, setSelectedStatus] = useState("Allocated");
  const [statusDept, setStatusDept] = useState("All");
  const [statusData, setStatusData] = useState(null);
  const [statusLoading, setStatusLoading] = useState(false);

  // Tab 3: By Category State
  const [selectedCategory, setSelectedCategory] = useState("Lab Equipment");
  const [categoryDept, setCategoryDept] = useState("All");
  const [categoryData, setCategoryData] = useState(null);
  const [categoryLoading, setCategoryLoading] = useState(false);

  // Tab 4: User Assets State
  const [selectedUserId, setSelectedUserId] = useState("");
  const [userAssetData, setUserAssetData] = useState(null);
  const [userLoading, setUserLoading] = useState(false);

  // Tab 5: Single Asset Lifecycle State
  const [assetSearch, setAssetSearch] = useState("");
  const [selectedAssetId, setSelectedAssetId] = useState("ast_seed_0");
  const [assetData, setAssetData] = useState(null);
  const [assetLoading, setAssetLoading] = useState(false);
  const [assetSubTab, setAssetSubTab] = useState("timeline");
  const [allAssets, setAllAssets] = useState([]);

  // Tab 6: Custom Reports (Templates) State
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [expandedPreviewId, setExpandedPreviewId] = useState(null);
  const [templatePreviews, setTemplatePreviews] = useState({});
  const [builderOpen, setBuilderOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);

  // Initial load: current user, overview data, metadata, users
  useEffect(() => {
    api("/auth/me").then(setCurrentUser).catch(() => {});
    api("/reports").then(setOverviewData).catch(() => {});
    api("/reports/metadata").then((m) => {
      setMetadata(m);
      if (m.departments?.length) setSelectedDept((d) => d || m.departments[0]);
      if (m.categories?.length) setSelectedCategory((c) => c || m.categories[0]);
    }).catch(() => {});
    api("/reports/users").then((u) => {
      setUsersList(u);
      if (u.length) setSelectedUserId((prev) => prev || u[0].user_id);
    }).catch(() => {});
    api("/assets").then((a) => {
      setAllAssets(a);
      if (a.length && !selectedAssetId) setSelectedAssetId(a[0].asset_id);
    }).catch(() => {});
  }, []);

  // Generic Download Helper
  const downloadReport = async (path, defaultFilename, format = "csv") => {
    setBusy(true);
    try {
      const sep = path.includes("?") ? "&" : "?";
      const res = await fetch(`${API}${path}${sep}format=${format}`, { credentials: "include" });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Download failed (${res.status})`);
      }
      const blob = await res.blob();
      let filename = defaultFilename.endsWith(`.${format}`) ? defaultFilename : `${defaultFilename}.${format}`;
      const disp = res.headers.get("Content-Disposition");
      if (disp && disp.includes("filename=")) {
        const m = disp.match(/filename="?([^"]+)"?/);
        if (m && m[1]) filename = m[1];
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(`Report downloaded as ${format.toUpperCase()}`);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  };

  // Tab 1 Fetcher
  const loadDeptReport = useCallback(async () => {
    if (!selectedDept) return;
    setDeptLoading(true);
    try {
      const d = await api(`/reports/department/${encodeURIComponent(selectedDept)}/${deptSubreport}?format=json`);
      setDeptData(d);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setDeptLoading(false);
    }
  }, [selectedDept, deptSubreport]);

  useEffect(() => {
    if (activeTab === "department") loadDeptReport();
  }, [activeTab, loadDeptReport]);

  // Tab 2 Fetcher (By Status)
  const loadStatusReport = useCallback(async () => {
    setStatusLoading(true);
    try {
      const d = await api(`/reports/assets-by-status?status=${encodeURIComponent(selectedStatus)}&department=${encodeURIComponent(statusDept)}&format=json`);
      setStatusData(d);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setStatusLoading(false);
    }
  }, [selectedStatus, statusDept]);

  useEffect(() => {
    if (activeTab === "status") loadStatusReport();
  }, [activeTab, loadStatusReport]);

  // Tab 3 Fetcher (By Category)
  const loadCategoryReport = useCallback(async () => {
    setCategoryLoading(true);
    try {
      const d = await api(`/reports/assets-by-category?category=${encodeURIComponent(selectedCategory)}&department=${encodeURIComponent(categoryDept)}&format=json`);
      setCategoryData(d);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setCategoryLoading(false);
    }
  }, [selectedCategory, categoryDept]);

  useEffect(() => {
    if (activeTab === "category") loadCategoryReport();
  }, [activeTab, loadCategoryReport]);

  // Tab 4 Fetcher (User Assets)
  const loadUserAssetReport = useCallback(async () => {
    if (!selectedUserId) return;
    setUserLoading(true);
    try {
      const d = await api(`/reports/user-assets/${encodeURIComponent(selectedUserId)}?format=json`);
      setUserAssetData(d);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setUserLoading(false);
    }
  }, [selectedUserId]);

  useEffect(() => {
    if (activeTab === "user") loadUserAssetReport();
  }, [activeTab, loadUserAssetReport]);

  // Tab 5 Fetcher (Single Asset)
  const loadSingleAssetReport = useCallback(async () => {
    if (!selectedAssetId) return;
    setAssetLoading(true);
    try {
      const d = await api(`/reports/asset/${encodeURIComponent(selectedAssetId)}?format=json`);
      setAssetData(d);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setAssetLoading(false);
    }
  }, [selectedAssetId]);

  useEffect(() => {
    if (activeTab === "single_asset") loadSingleAssetReport();
  }, [activeTab, loadSingleAssetReport]);

  // Tab 6 Fetcher (Custom Reports / Templates)
  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    try {
      const t = await api("/reports/templates");
      setTemplates(t);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setTemplatesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "custom") loadTemplates();
  }, [activeTab, loadTemplates]);

  const toggleTemplatePreview = async (templateId) => {
    if (expandedPreviewId === templateId) {
      setExpandedPreviewId(null);
      return;
    }
    setExpandedPreviewId(templateId);
    if (!templatePreviews[templateId]) {
      try {
        const prev = await api(`/reports/templates/${templateId}/preview`);
        setTemplatePreviews((p) => ({ ...p, [templateId]: prev }));
      } catch (e) {
        toast.error(`Preview failed: ${e.message}`);
      }
    }
  };

  const handleDeleteTemplate = async (templateId, name) => {
    if (!window.confirm(`Are you sure you want to remove template "${name}"?`)) return;
    try {
      await api(`/reports/templates/${templateId}`, { method: "DELETE" });
      toast.success("Template deleted");
      loadTemplates();
    } catch (e) {
      toast.error(e.message);
    }
  };

  const filteredAssetSuggestions = assetSearch.trim()
    ? allAssets.filter((a) =>
        (a.name || "").toLowerCase().includes(assetSearch.toLowerCase()) ||
        (a.tag || "").toLowerCase().includes(assetSearch.toLowerCase()) ||
        (a.serial || "").toLowerCase().includes(assetSearch.toLowerCase())
      ).slice(0, 8)
    : [];

  return (
    <>
      <PageHeader
        eyebrow="CAMPUS INTELLIGENCE"
        title="Reports & Analytics"
        description="Comprehensive departmental registers, operational traces, custom templates, and accreditation evidence."
        action={
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            {currentUser?.role === "Admin" && (
              <button
                data-testid="create-template-top-btn"
                className="primary-btn"
                onClick={() => { setEditingTemplate(null); setBuilderOpen(true); }}
              >
                <Plus size={14} /> New Template
              </button>
            )}
            <button
              data-testid="report-download-csv"
              className="secondary-btn"
              disabled={busy}
              onClick={() => downloadReport("/reports/accreditation/download", "assetflow_accreditation", "csv")}
            >
              <Download size={13} /> Accreditation CSV
            </button>
            <button
              data-testid="report-download-pdf"
              className="secondary-btn"
              disabled={busy}
              onClick={() => downloadReport("/reports/accreditation/download", "assetflow_accreditation", "pdf")}
            >
              <FileText size={13} /> Accreditation PDF
            </button>
          </div>
        }
      />

      {/* Top Metric Cards */}
      {overviewData && (
        <div className="metric-grid">
          <div className="metric">
            <div className="metric-top"><span>Total Tracked</span><Box size={16} /></div>
            <strong>{overviewData.total}</strong>
            <small>Across all campus departments</small>
          </div>
          {Object.entries(overviewData.status_counts).slice(0, 3).map(([k, v]) => (
            <div className="metric" key={k}>
              <div className="metric-top"><span>{k}</span><Activity size={16} /></div>
              <strong>{v}</strong>
              <small>Current inventory count</small>
            </div>
          ))}
        </div>
      )}

      {/* Report Center Shell */}
      <section className="report-center-shell">
        {/* Navigation Tabs */}
        <div className="report-tabs" role="tablist">
          <button
            data-testid="report-tab-department"
            className={`report-tab-btn ${activeTab === "department" ? "active" : ""}`}
            onClick={() => setActiveTab("department")}
          >
            <Package size={14} /> Department Reports
          </button>
          <button
            data-testid="report-tab-status"
            className={`report-tab-btn ${activeTab === "status" ? "active" : ""}`}
            onClick={() => setActiveTab("status")}
          >
            <Activity size={14} /> By Status
          </button>
          <button
            data-testid="report-tab-category"
            className={`report-tab-btn ${activeTab === "category" ? "active" : ""}`}
            onClick={() => setActiveTab("category")}
          >
            <Filter size={14} /> By Category
          </button>
          <button
            data-testid="report-tab-user"
            className={`report-tab-btn ${activeTab === "user" ? "active" : ""}`}
            onClick={() => setActiveTab("user")}
          >
            <User size={14} /> User & No-Dues
          </button>
          <button
            data-testid="report-tab-single-asset"
            className={`report-tab-btn ${activeTab === "single_asset" ? "active" : ""}`}
            onClick={() => setActiveTab("single_asset")}
          >
            <Sparkles size={14} /> Single Asset Lifecycle
          </button>
          <button
            data-testid="report-tab-custom"
            className={`report-tab-btn ${activeTab === "custom" ? "active" : ""}`}
            onClick={() => setActiveTab("custom")}
          >
            <SlidersHorizontal size={14} /> Custom Reports
            <span className="report-tab-badge">{templates.length}</span>
          </button>
          <button
            data-testid="report-tab-accreditation"
            className={`report-tab-btn ${activeTab === "accreditation" ? "active" : ""}`}
            onClick={() => setActiveTab("accreditation")}
          >
            <ClipboardCheck size={14} /> Accreditation & Utilization
          </button>
        </div>

        {/* ============================================================
            TAB 1: Department Reports
            ============================================================ */}
        {activeTab === "department" && (
          <div style={{ display: "grid", gap: 16 }}>
            <div className="report-controls-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
                <div className="report-subtypes">
                  <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--mute)", textTransform: "uppercase" }}>Type:</span>
                  <button
                    data-testid="report-subtype-assets"
                    className={`report-subtype-pill ${deptSubreport === "assets" ? "active" : ""}`}
                    onClick={() => setDeptSubreport("assets")}
                  >
                    <Package size={13} /> Asset Register
                  </button>
                  <button
                    data-testid="report-subtype-maintenance"
                    className={`report-subtype-pill ${deptSubreport === "maintenance" ? "active" : ""}`}
                    onClick={() => setDeptSubreport("maintenance")}
                  >
                    <Wrench size={13} /> Maintenance History
                  </button>
                  <button
                    data-testid="report-subtype-bookings"
                    className={`report-subtype-pill ${deptSubreport === "bookings" ? "active" : ""}`}
                    onClick={() => setDeptSubreport("bookings")}
                  >
                    <Clock3 size={13} /> Reservation Log
                  </button>
                </div>

                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    data-testid="dept-download-csv"
                    className="secondary-btn"
                    disabled={busy || deptLoading}
                    onClick={() => downloadReport(`/reports/department/${encodeURIComponent(selectedDept)}/${deptSubreport}`, `${selectedDept}_${deptSubreport}`, "csv")}
                  >
                    <Download size={13} /> Export CSV
                  </button>
                  <button
                    data-testid="dept-download-pdf"
                    className="primary-btn"
                    disabled={busy || deptLoading}
                    onClick={() => downloadReport(`/reports/department/${encodeURIComponent(selectedDept)}/${deptSubreport}`, `${selectedDept}_${deptSubreport}`, "pdf")}
                  >
                    <FileText size={13} /> Export PDF
                  </button>
                </div>
              </div>

              <div className="report-filter-grid">
                <div className="report-filter-item">
                  <label>Select Department</label>
                  <select
                    data-testid="report-department-select"
                    value={selectedDept}
                    onChange={(e) => setSelectedDept(e.target.value)}
                  >
                    {metadata.departments.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>

                {deptData && (
                  <div style={{ display: "flex", gap: 16, alignItems: "center", marginLeft: "auto", flexWrap: "wrap" }}>
                    <div className="report-count-indicator">Total: <b>{deptData.total || 0}</b></div>
                    {deptSubreport === "assets" && (
                      <>
                        <div className="report-count-indicator">Allocated: <b style={{ color: "var(--link)" }}>{deptData.allocated || 0}</b></div>
                        <div className="report-count-indicator">Available: <b style={{ color: "var(--success)" }}>{deptData.available || 0}</b></div>
                        <div className="report-count-indicator">Under Maint: <b style={{ color: "var(--error)" }}>{deptData.maintenance || 0}</b></div>
                      </>
                    )}
                    {deptSubreport === "maintenance" && (
                      <>
                        <div className="report-count-indicator">Open / In Progress: <b style={{ color: "var(--warning)" }}>{deptData.open || 0}</b></div>
                        <div className="report-count-indicator">Resolved: <b style={{ color: "var(--success)" }}>{deptData.resolved || 0}</b></div>
                      </>
                    )}
                    {deptSubreport === "bookings" && (
                      <div className="report-count-indicator">Confirmed: <b style={{ color: "var(--success)" }}>{deptData.confirmed || 0}</b></div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <ReportPreviewTable
              headers={deptData?.headers || []}
              rows={deptData?.rows || []}
              total={deptData?.total || 0}
              loading={deptLoading}
              title={`${selectedDept} · ${deptSubreport === "assets" ? "Asset Register" : deptSubreport === "maintenance" ? "Work Order Log" : "Booking Records"}`}
              emptyMessage={`No ${deptSubreport} records recorded for ${selectedDept}`}
            />
          </div>
        )}

        {/* ============================================================
            TAB 2: By Status
            ============================================================ */}
        {activeTab === "status" && (
          <div style={{ display: "grid", gap: 16 }}>
            <div className="report-controls-card">
              <div className="report-filter-grid">
                <div className="report-filter-item">
                  <label>Status</label>
                  <select
                    data-testid="report-status-select"
                    value={selectedStatus}
                    onChange={(e) => setSelectedStatus(e.target.value)}
                  >
                    <option value="All">All Operational Statuses</option>
                    {["Available", "Allocated", "Under Maintenance", "Lost", "Retired"].map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>

                <div className="report-filter-item">
                  <label>Department Filter</label>
                  <select
                    data-testid="report-status-dept-select"
                    value={statusDept}
                    onChange={(e) => setStatusDept(e.target.value)}
                  >
                    <option value="All">All Departments</option>
                    {metadata.departments.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>

                <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
                  <button
                    data-testid="status-download-csv"
                    className="secondary-btn"
                    disabled={busy || statusLoading}
                    onClick={() => downloadReport(`/reports/assets-by-status?status=${encodeURIComponent(selectedStatus)}&department=${encodeURIComponent(statusDept)}`, `assets_status_${selectedStatus.toLowerCase()}`, "csv")}
                  >
                    <Download size={13} /> Export CSV
                  </button>
                  <button
                    data-testid="status-download-pdf"
                    className="primary-btn"
                    disabled={busy || statusLoading}
                    onClick={() => downloadReport(`/reports/assets-by-status?status=${encodeURIComponent(selectedStatus)}&department=${encodeURIComponent(statusDept)}`, `assets_status_${selectedStatus.toLowerCase()}`, "pdf")}
                  >
                    <FileText size={13} /> Export PDF
                  </button>
                </div>
              </div>
            </div>

            <ReportPreviewTable
              headers={statusData?.headers || []}
              rows={statusData?.rows || []}
              total={statusData?.total || 0}
              loading={statusLoading}
              title={`Status Filter · ${selectedStatus} ${statusDept !== "All" ? `(${statusDept})` : "(Campus-Wide)"}`}
              emptyMessage={`No assets currently marked as "${selectedStatus}" in selected department`}
            />
          </div>
        )}

        {/* ============================================================
            TAB 3: By Category
            ============================================================ */}
        {activeTab === "category" && (
          <div style={{ display: "grid", gap: 16 }}>
            <div className="report-controls-card">
              <div className="report-filter-grid">
                <div className="report-filter-item">
                  <label>Category</label>
                  <select
                    data-testid="report-category-select"
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                  >
                    <option value="All">All Categories</option>
                    {metadata.categories.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>

                <div className="report-filter-item">
                  <label>Department Filter</label>
                  <select
                    data-testid="report-category-dept-select"
                    value={categoryDept}
                    onChange={(e) => setCategoryDept(e.target.value)}
                  >
                    <option value="All">All Departments</option>
                    {metadata.departments.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>

                <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
                  <button
                    data-testid="category-download-csv"
                    className="secondary-btn"
                    disabled={busy || categoryLoading}
                    onClick={() => downloadReport(`/reports/assets-by-category?category=${encodeURIComponent(selectedCategory)}&department=${encodeURIComponent(categoryDept)}`, `assets_cat_${selectedCategory.toLowerCase()}`, "csv")}
                  >
                    <Download size={13} /> Export CSV
                  </button>
                  <button
                    data-testid="category-download-pdf"
                    className="primary-btn"
                    disabled={busy || categoryLoading}
                    onClick={() => downloadReport(`/reports/assets-by-category?category=${encodeURIComponent(selectedCategory)}&department=${encodeURIComponent(categoryDept)}`, `assets_cat_${selectedCategory.toLowerCase()}`, "pdf")}
                  >
                    <FileText size={13} /> Export PDF
                  </button>
                </div>
              </div>
            </div>

            <ReportPreviewTable
              headers={categoryData?.headers || []}
              rows={categoryData?.rows || []}
              total={categoryData?.total || 0}
              loading={categoryLoading}
              title={`Category Filter · ${selectedCategory} ${categoryDept !== "All" ? `(${categoryDept})` : "(Campus-Wide)"}`}
              emptyMessage={`No assets categorized under "${selectedCategory}"`}
            />
          </div>
        )}

        {/* ============================================================
            TAB 4: User Assets & Clearance
            ============================================================ */}
        {activeTab === "user" && (
          <div style={{ display: "grid", gap: 16 }}>
            <div className="report-controls-card">
              <div className="report-filter-grid">
                <div className="report-filter-item" style={{ flex: 2 }}>
                  <label>Select User / Employee / Student</label>
                  <select
                    data-testid="report-user-select"
                    value={selectedUserId}
                    onChange={(e) => setSelectedUserId(e.target.value)}
                  >
                    {usersList.map((u) => (
                      <option key={u.user_id} value={u.user_id}>
                        {u.name} ({u.role} · {u.department || "No Dept"}) — {u.email}
                      </option>
                    ))}
                  </select>
                </div>

                {userAssetData && (
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    {userAssetData.total > 0 ? (
                      <span className="status status-pending" data-testid="user-clearance-status">
                        <i></i> PENDING RETURN ({userAssetData.total} ITEMS HELD)
                      </span>
                    ) : (
                      <span className="status status-available" data-testid="user-clearance-status">
                        <i></i> CLEARED (0 HELD ASSETS)
                      </span>
                    )}
                  </div>
                )}

                <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
                  <button
                    data-testid="user-download-csv"
                    className="secondary-btn"
                    disabled={busy || userLoading || !selectedUserId}
                    onClick={() => downloadReport(`/reports/user-assets/${encodeURIComponent(selectedUserId)}`, `user_${selectedUserId}_assets`, "csv")}
                  >
                    <Download size={13} /> Export CSV
                  </button>
                  <button
                    data-testid="user-download-pdf"
                    className="primary-btn"
                    disabled={busy || userLoading || !selectedUserId}
                    onClick={() => downloadReport(`/reports/user-assets/${encodeURIComponent(selectedUserId)}`, `user_${selectedUserId}_clearance`, "pdf")}
                  >
                    <FileText size={13} /> Clearance Certificate PDF
                  </button>
                </div>
              </div>
            </div>

            <ReportPreviewTable
              headers={userAssetData?.headers || []}
              rows={userAssetData?.rows || []}
              total={userAssetData?.total || 0}
              loading={userLoading}
              title={`Personal Asset Holdings · ${userAssetData?.user?.name || selectedUserId}`}
              emptyMessage="This user currently holds 0 active campus assets. Ready for No-Dues clearance."
            />
          </div>
        )}

        {/* ============================================================
            TAB 5: Single Asset Lifecycle Report
            ============================================================ */}
        {activeTab === "single_asset" && (
          <div style={{ display: "grid", gap: 20 }}>
            <div className="report-controls-card">
              <div className="asset-search-card">
                <div className="asset-search-input">
                  <Search size={15} />
                  <input
                    data-testid="report-asset-search"
                    placeholder="Search asset by Tag, Name, or Serial Number…"
                    value={assetSearch}
                    onChange={(e) => setAssetSearch(e.target.value)}
                  />
                </div>

                <div className="asset-chips-row">
                  <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--mute)", textTransform: "uppercase" }}>Quick Pick:</span>
                  {allAssets.slice(0, 5).map((a) => (
                    <button
                      key={a.asset_id}
                      data-testid={`quick-asset-${a.tag}`}
                      className={`asset-tag-chip ${selectedAssetId === a.asset_id ? "active" : ""}`}
                      onClick={() => { setSelectedAssetId(a.asset_id); setAssetSearch(""); }}
                    >
                      {a.tag} · {a.name}
                    </button>
                  ))}
                </div>
              </div>

              {filteredAssetSuggestions.length > 0 && (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", padding: "10px 0", borderTop: "1px solid var(--hairline)" }}>
                  <span style={{ fontSize: 11, color: "var(--mute)" }}>Matches:</span>
                  {filteredAssetSuggestions.map((a) => (
                    <button
                      key={a.asset_id}
                      className="link-btn"
                      style={{ fontSize: 12, padding: "2px 8px", background: "var(--hairline-soft)", borderRadius: 4 }}
                      onClick={() => { setSelectedAssetId(a.asset_id); setAssetSearch(""); }}
                    >
                      <b>{a.tag}</b> — {a.name} ({a.department})
                    </button>
                  ))}
                </div>
              )}
            </div>

            {assetLoading && (
              <div className="loading" style={{ padding: 60 }}><RefreshCw size={24} className="animate-spin" /> Loading full asset lifecycle trace…</div>
            )}

            {!assetLoading && assetData && (
              <div style={{ display: "grid", gap: 18 }} data-testid="single-asset-report-view">
                {/* Hero Asset Profile Card */}
                <div className="asset-hero-card">
                  <div className="asset-hero-top">
                    <div className="asset-hero-title">
                      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                        <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--mute)" }}>{assetData.asset.tag}</span>
                        <span className={`status status-${(assetData.asset.status || "").toLowerCase().replace(" ", "-")}`}>
                          <i></i>{assetData.asset.status}
                        </span>
                        {assetData.asset.bookable && (
                          <span className="template-chip" style={{ color: "var(--violet)", borderColor: "rgba(121,40,202,.3)" }}>Bookable</span>
                        )}
                      </div>
                      <h2>{assetData.asset.name}</h2>
                      <p className="muted" style={{ margin: 0 }}>
                        {assetData.asset.category} · Located at {assetData.asset.location} · {assetData.asset.department}
                      </p>
                    </div>

                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button
                        data-testid="asset-download-csv"
                        className="secondary-btn"
                        disabled={busy}
                        onClick={() => downloadReport(`/reports/asset/${selectedAssetId}`, `asset_${assetData.asset.tag}_lifecycle`, "csv")}
                      >
                        <Download size={13} /> Export Lifecycle CSV
                      </button>
                      <button
                        data-testid="asset-download-pdf"
                        className="primary-btn"
                        disabled={busy}
                        onClick={() => downloadReport(`/reports/asset/${selectedAssetId}`, `asset_${assetData.asset.tag}_lifecycle`, "pdf")}
                      >
                        <FileText size={13} /> Full Audit Report PDF
                      </button>
                    </div>
                  </div>

                  {/* 2x4 Key Specs */}
                  <div className="asset-specs-grid">
                    <div className="asset-spec-item">
                      <small>Current Holder</small>
                      <b>{assetData.asset.holder || "Unassigned"}</b>
                    </div>
                    <div className="asset-spec-item">
                      <small>Serial Number</small>
                      <b className="mono">{assetData.asset.serial || "—"}</b>
                    </div>
                    <div className="asset-spec-item">
                      <small>Purchase Cost</small>
                      <b>{assetData.asset.purchase_cost ? `Rs. ${Number(assetData.asset.purchase_cost).toLocaleString()}` : "—"}</b>
                    </div>
                    <div className="asset-spec-item">
                      <small>Purchase Date</small>
                      <b>{assetData.asset.purchase_date || "—"}</b>
                    </div>
                    <div className="asset-spec-item">
                      <small>Supplier</small>
                      <b>{assetData.asset.supplier || "—"}</b>
                    </div>
                    <div className="asset-spec-item">
                      <small>Warranty End</small>
                      <b>{assetData.asset.warranty_end || "—"}</b>
                    </div>
                  </div>

                  {/* Lifecycle Stats Counters */}
                  <div className="lifecycle-stats-row">
                    <div className="lifecycle-stat">
                      <span>{assetData.metrics?.total_events || 0}</span>
                      <small>Activity Events</small>
                    </div>
                    <div className="lifecycle-stat">
                      <span>{assetData.metrics?.total_maintenance || 0}</span>
                      <small>Repair Orders</small>
                    </div>
                    <div className="lifecycle-stat">
                      <span style={{ color: (assetData.metrics?.open_maintenance || 0) > 0 ? "var(--warning)" : "var(--success)" }}>
                        {assetData.metrics?.open_maintenance || 0}
                      </span>
                      <small>Open Repairs</small>
                    </div>
                    <div className="lifecycle-stat">
                      <span>{assetData.metrics?.total_bookings || 0}</span>
                      <small>Reservations</small>
                    </div>
                    <div className="lifecycle-stat">
                      <span>{assetData.metrics?.audit_verifications || 0}</span>
                      <small>Physical Audits</small>
                    </div>
                  </div>
                </div>

                {/* Sub-tabs for detailed logs */}
                <div className="surface" style={{ padding: 20 }}>
                  <div style={{ display: "flex", gap: 6, marginBottom: 16, borderBottom: "1px solid var(--hairline)", paddingBottom: 10 }}>
                    <button
                      className={`report-tab-btn ${assetSubTab === "timeline" ? "active" : ""}`}
                      onClick={() => setAssetSubTab("timeline")}
                      data-testid="asset-subtab-timeline"
                    >
                      <Activity size={13} /> Activity Trail ({assetData.activity?.length || 0})
                    </button>
                    <button
                      className={`report-tab-btn ${assetSubTab === "maintenance" ? "active" : ""}`}
                      onClick={() => setAssetSubTab("maintenance")}
                      data-testid="asset-subtab-maintenance"
                    >
                      <Wrench size={13} /> Maintenance Logs ({assetData.maintenance?.length || 0})
                    </button>
                    <button
                      className={`report-tab-btn ${assetSubTab === "bookings" ? "active" : ""}`}
                      onClick={() => setAssetSubTab("bookings")}
                      data-testid="asset-subtab-bookings"
                    >
                      <Clock3 size={13} /> Booking Logs ({assetData.bookings?.length || 0})
                    </button>
                    <button
                      className={`report-tab-btn ${assetSubTab === "audits" ? "active" : ""}`}
                      onClick={() => setAssetSubTab("audits")}
                      data-testid="asset-subtab-audits"
                    >
                      <ClipboardCheck size={13} /> Physical Audits ({assetData.audits?.length || 0})
                    </button>
                  </div>

                  {assetSubTab === "timeline" && (
                    <div>
                      {(!assetData.activity || assetData.activity.length === 0) ? (
                        <div className="report-table-empty">No activity events recorded for this asset yet.</div>
                      ) : (
                        <div className="lifecycle-timeline">
                          {assetData.activity.map((ev, i) => (
                            <div className="timeline-item" key={ev.event_id || i}>
                              <div className={`timeline-dot ${i === 0 ? "active" : ""}`}></div>
                              <div className="timeline-content">
                                <div className="timeline-meta">
                                  <span>{ev.timestamp ? new Date(ev.timestamp).toLocaleString() : "—"}</span>
                                  <span className="template-chip">{ev.actor || "System"}</span>
                                </div>
                                <div className="timeline-action">{ev.action}</div>
                                {ev.metadata && Object.keys(ev.metadata).length > 0 && (
                                  <div className="timeline-details">
                                    {Object.entries(ev.metadata).map(([k, v]) => `${k}: ${v}`).join(" · ")}
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {assetSubTab === "maintenance" && (
                    <ReportPreviewTable
                      headers={["Request ID", "Priority", "Status", "Description", "Raised By", "Created", "Resolved"]}
                      rows={(assetData.maintenance || []).map((m) => [
                        m.request_id || "",
                        m.priority || "Medium",
                        m.status || "Open",
                        m.description || "—",
                        m.raised_by || "—",
                        (m.created_at || "").slice(0, 10),
                        (m.resolved_at || "—").slice(0, 10)
                      ])}
                      total={assetData.maintenance?.length || 0}
                      title="Maintenance & Work Orders"
                      emptyMessage="No maintenance or repair work orders logged for this asset"
                    />
                  )}

                  {assetSubTab === "bookings" && (
                    <ReportPreviewTable
                      headers={["Booking ID", "Date", "Slot", "Event / Purpose", "Requested By", "Status"]}
                      rows={(assetData.bookings || []).map((b) => [
                        b.booking_id || "",
                        b.date || "",
                        `${b.start_time || ""} - ${b.end_time || ""}`,
                        b.event_title || b.purpose || "—",
                        b.requested_by || "—",
                        b.status || "Confirmed"
                      ])}
                      total={assetData.bookings?.length || 0}
                      title="Room / Resource Booking History"
                      emptyMessage="No reservations recorded for this asset"
                    />
                  )}

                  {assetSubTab === "audits" && (
                    <ReportPreviewTable
                      headers={["Audit ID", "Department", "Period", "Verification", "Auditor Notes", "Status"]}
                      rows={(assetData.audits || []).flatMap((a) =>
                        (a.items || [])
                          .filter((it) => it.asset_id === assetData.asset.asset_id || it.tag === assetData.asset.tag)
                          .map((it) => [
                            a.audit_id || "",
                            a.department || "",
                            a.period || "",
                            it.verification || "Pending",
                            it.note || "—",
                            a.status || ""
                          ])
                      )}
                      total={(assetData.audits || []).length}
                      title="Physical Audit Cycle Verification Log"
                      emptyMessage="No physical audit cycles recorded for this asset yet"
                    />
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ============================================================
            TAB 6: Custom Reports (Admin Template Builder)
            ============================================================ */}
        {activeTab === "custom" && (
          <div style={{ display: "grid", gap: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
              <div>
                <h3 style={{ margin: "0 0 4px", fontSize: 18 }}>Custom Report Templates</h3>
                <p className="muted" style={{ margin: 0 }}>
                  Pre-configured data extractions published by campus administrators.
                </p>
              </div>

              {currentUser?.role === "Admin" && (
                <button
                  data-testid="create-template-btn"
                  className="primary-btn"
                  onClick={() => { setEditingTemplate(null); setBuilderOpen(true); }}
                >
                  <Plus size={14} /> Create Report Template
                </button>
              )}
            </div>

            {templatesLoading ? (
              <div className="loading" style={{ padding: 40 }}><RefreshCw size={20} className="animate-spin" /> Loading custom templates…</div>
            ) : templates.length === 0 ? (
              <div className="surface report-table-empty">
                <SlidersHorizontal size={28} style={{ opacity: 0.4, margin: "0 auto 12px", display: "block" }} />
                <b>No custom report templates available</b>
                <p style={{ margin: "6px 0 0", color: "var(--mute)", fontSize: 13 }}>
                  {currentUser?.role === "Admin"
                    ? "Click '+ Create Report Template' to design your first custom report."
                    : "Your administrator has not published any templates for your role yet."}
                </p>
              </div>
            ) : (
              <div className="template-grid" data-testid="custom-templates-grid">
                {templates.map((tmpl) => {
                  const isExpanded = expandedPreviewId === tmpl.template_id;
                  const preview = templatePreviews[tmpl.template_id];
                  const sourceClass = (tmpl.data_source || "assets").toLowerCase();

                  return (
                    <div className="template-card" key={tmpl.template_id} data-testid={`template-card-${tmpl.template_id}`}>
                      <div className="template-card-top">
                        <div>
                          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                            <span className={`template-badge ${sourceClass}`}>
                              {tmpl.data_source}
                            </span>
                            <span className="mono" style={{ fontSize: 11, color: "var(--mute)" }}>{tmpl.template_id}</span>
                          </div>
                          <h4>{tmpl.name}</h4>
                          <p>{tmpl.description || "No description provided."}</p>
                        </div>

                        {currentUser?.role === "Admin" && (
                          <div style={{ display: "flex", gap: 4 }}>
                            <button
                              className="icon-btn"
                              style={{ width: 28, height: 28 }}
                              title="Edit template"
                              onClick={() => { setEditingTemplate(tmpl); setBuilderOpen(true); }}
                              data-testid={`edit-template-${tmpl.template_id}`}
                            >
                              <Pencil size={13} />
                            </button>
                            <button
                              className="icon-btn"
                              style={{ width: 28, height: 28, color: "var(--error)" }}
                              title="Delete template"
                              onClick={() => handleDeleteTemplate(tmpl.template_id, tmpl.name)}
                              data-testid={`delete-template-${tmpl.template_id}`}
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Meta chips */}
                      <div className="template-meta-row">
                        <span className="template-chip">{tmpl.columns?.length || 0} columns</span>
                        {tmpl.filters && Object.keys(tmpl.filters).length > 0 && (
                          <span className="template-chip">
                            Filters: {Object.entries(tmpl.filters).map(([k, v]) => `${k}=${v}`).join(", ")}
                          </span>
                        )}
                        {tmpl.sort_by && (
                          <span className="template-chip">Sort: {tmpl.sort_by} ({tmpl.sort_order || "asc"})</span>
                        )}
                      </div>

                      <div className="template-meta-row">
                        <span style={{ fontSize: 11, color: "var(--mute)" }}>Audience:</span>
                        {(tmpl.access_roles || ["Admin"]).map((r) => (
                          <span key={r} className="template-chip" style={{ fontSize: 10 }}>{r}</span>
                        ))}
                      </div>

                      {/* Actions */}
                      <div className="template-card-footer">
                        <span className="template-author">
                          By {tmpl.created_by_name || "Admin"} · {fmtRelative(tmpl.created_at)}
                        </span>

                        <div style={{ display: "flex", gap: 6 }}>
                          <button
                            data-testid={`template-preview-btn-${tmpl.template_id}`}
                            className="secondary-btn compact"
                            onClick={() => toggleTemplatePreview(tmpl.template_id)}
                          >
                            <Eye size={12} /> {isExpanded ? "Hide" : "Preview"}
                          </button>
                          <button
                            data-testid={`template-download-csv-${tmpl.template_id}`}
                            className="secondary-btn compact"
                            disabled={busy}
                            onClick={() => downloadReport(`/reports/templates/${tmpl.template_id}/download`, tmpl.name, "csv")}
                          >
                            <Download size={12} /> CSV
                          </button>
                          <button
                            data-testid={`template-download-pdf-${tmpl.template_id}`}
                            className="primary-btn compact"
                            disabled={busy}
                            onClick={() => downloadReport(`/reports/templates/${tmpl.template_id}/download`, tmpl.name, "pdf")}
                          >
                            <FileText size={12} /> PDF
                          </button>
                        </div>
                      </div>

                      {/* Inline Expanded Preview */}
                      {isExpanded && (
                        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px dashed var(--hairline)" }}>
                          {preview ? (
                            <ReportPreviewTable
                              headers={preview.headers}
                              rows={preview.preview_rows}
                              total={preview.total}
                              title={`${tmpl.name} (First 20 records)`}
                            />
                          ) : (
                            <div className="loading" style={{ padding: 20 }}><RefreshCw size={14} className="animate-spin" /> Loading preview data…</div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ============================================================
            TAB 7: Accreditation Evidence & Department Utilization
            ============================================================ */}
        {activeTab === "accreditation" && (
          <div style={{ display: "grid", gap: 20 }}>
            {/* Accreditation Global Card */}
            <section className="surface" data-testid="accreditation-report-card">
              <div className="section-title">
                <div>
                  <p className="eyebrow">GLOBAL AUDIT & ACCREDITATION</p>
                  <h3>NAAC / NBA Accreditation Evidence Extract</h3>
                  <p className="muted" style={{ margin: "4px 0 0" }}>
                    Official institutional inventory summary file including asset counts, departmental distributions, and maintenance metrics.
                  </p>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    data-testid="accreditation-csv-btn"
                    className="secondary-btn"
                    disabled={busy}
                    onClick={() => downloadReport("/reports/accreditation/download", "assetflow_accreditation", "csv")}
                  >
                    <Download size={13} /> Export CSV
                  </button>
                  <button
                    data-testid="accreditation-pdf-btn"
                    className="primary-btn"
                    disabled={busy}
                    onClick={() => downloadReport("/reports/accreditation/download", "assetflow_accreditation", "pdf")}
                  >
                    <FileText size={13} /> Export PDF
                  </button>
                </div>
              </div>
            </section>

            {/* Department Utilization Bar Charts (Preserved from existing design) */}
            {overviewData && (
              <section className="surface report-table" data-testid="utilization-by-dept-section">
                <div className="section-title">
                  <div>
                    <p className="eyebrow">UTILIZATION BY DEPARTMENT</p>
                    <h3>Where resources are allocated across campus</h3>
                  </div>
                </div>
                {overviewData.departments.map((x) => {
                  const pct = x.total ? Math.round((x.allocated / x.total) * 100) : 0;
                  return (
                    <div data-testid="report-department-row" className="report-row" key={x.name}>
                      <div>
                        <b>{x.name}</b>
                        <small>{x.allocated} of {x.total} assets currently allocated</small>
                      </div>
                      <div className="progress"><span style={{ width: `${pct}%` }} /></div>
                      <strong>{pct}%</strong>
                    </div>
                  );
                })}
              </section>
            )}
          </div>
        )}
      </section>

      {/* Admin Report Builder Modal */}
      {builderOpen && (
        <ReportTemplateBuilderModal
          template={editingTemplate}
          onClose={() => { setBuilderOpen(false); setEditingTemplate(null); }}
          onSaved={() => { loadTemplates(); }}
        />
      )}
    </>
  );
}


function pad2(n) { return String(n).padStart(2, "0"); }
function dayISO(offset) {
  const d = new Date(Date.now() + offset * 86400000);
  return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())}`;
}
function to12h(t) {
  if (!t || !t.includes(":")) return t || "";
  const [h, m] = t.split(":").map(Number);
  const ap = h >= 12 ? "PM" : "AM";
  const hh = h % 12 === 0 ? 12 : h % 12;
  return `${pad2(hh)}:${pad2(m)} ${ap}`;
}
function defaultBookingWindow() {
  const s = new Date(Date.now() + 3600000); s.setMinutes(0, 0, 0);
  const e = new Date(s.getTime() + 3600000);
  const fmt = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
  return { start: fmt(s), end: fmt(e) };
}

function Bookings() {
  const [resources, setResources] = useState([]);
  const [selected, setSelected] = useState("");
  const [items, setItems] = useState([]);
  const win = defaultBookingWindow();
  const [form, setForm] = useState({ start: win.start, end: win.end, event_title: "", department: "", attendees: "", contact: "", purpose: "" });
  const [busy, setBusy] = useState(false);

  const loadBookings = useCallback(() => api("/bookings").then(setItems).catch((e) => toast.error(e.message)), []);
  useEffect(() => {
    api("/assets").then((a) => {
      const bookable = a.filter((x) => x.bookable);
      const list = bookable.length ? bookable : a;
      setResources(list);
      if (list.length) setSelected((prev) => prev || list[0].asset_id);
    }).catch((e) => toast.error(e.message));
    loadBookings();
  }, [loadBookings]);

  const resource = resources.find((r) => r.asset_id === selected);

  const save = async (e) => {
    e.preventDefault();
    if (!resource) { toast.error("Pick a resource first"); return; }
    if (!form.start || !form.end) { toast.error("Choose a start and end time"); return; }
    const date = form.start.slice(0, 10);
    if (form.end.slice(0, 10) !== date) { toast.error("Start and end must be on the same day"); return; }
    const start_time = form.start.slice(11, 16), end_time = form.end.slice(11, 16);
    if (end_time <= start_time) { toast.error("End time must be after the start time"); return; }
    if (!form.purpose.trim()) { toast.error("Please add a purpose"); return; }
    setBusy(true);
    try {
      await api("/bookings", { method: "POST", body: JSON.stringify({
        resource_id: resource.asset_id, resource_name: resource.name, location: resource.location || "", category: resource.category || "",
        date, start_time, end_time, purpose: form.purpose.trim(),
        event_title: form.event_title.trim(), department: form.department.trim(), attendees: Number(form.attendees) || 0, contact: form.contact.trim(),
      }) });
      toast.success("Booking confirmed and logged");
      const w = defaultBookingWindow();
      setForm({ start: w.start, end: w.end, event_title: "", department: "", attendees: "", contact: "", purpose: "" });
      loadBookings();
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };

  const cancel = async (b) => {
    try { await api(`/bookings/${b.booking_id}`, { method: "DELETE" }); toast.success("Booking cancelled"); loadBookings(); }
    catch (e) { toast.error(e.message); }
  };

  const days = Array.from({ length: 7 }, (_, i) => {
    const iso = dayISO(i);
    const d = new Date(iso + "T00:00:00Z");
    return { iso, dow: d.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" }).toUpperCase(), dnum: d.getUTCDate() };
  });
  const now = new Date();
  const bookingsFor = (iso) => items.filter((b) => b.resource_id === selected && b.date === iso).sort((a, b) => (a.start_time || "").localeCompare(b.start_time || ""));

  return (
    <>
      <PageHeader eyebrow="BOOKING" title="Resource booking" description="Reserve rooms, projectors and vehicles by time-slot." />
      <div className="booking-layout">
        <div className="booking-main">
          <section className="surface" data-testid="booking-resource-card">
            <p className="eyebrow" style={{ marginBottom: 10 }}>Resource</p>
            <div className="res-select-wrap">
              <select data-testid="booking-resource-select" className="res-select" value={selected} onChange={(e) => setSelected(e.target.value)}>
                {resources.length === 0 && <option value="">No bookable resources</option>}
                {resources.map((r) => <option key={r.asset_id} value={r.asset_id}>{r.tag} · {r.name}</option>)}
              </select>
              <ChevronRight size={16} className="res-chevron" />
            </div>
            <div className="res-meta"><MapPin size={14} /> <span>{resource?.location || "—"}</span>{resource?.category && <span className="res-cat">{resource.category}</span>}</div>
          </section>

          <section className="surface" data-testid="booking-agenda" style={{ marginTop: 20 }}>
            <div className="section-title"><div><p className="eyebrow">Calendar</p><h3>Next 7 days</h3></div></div>
            {days.map((day) => {
              const list = bookingsFor(day.iso);
              return (
                <div className="agenda-day" key={day.iso}>
                  <div className="agenda-date"><div className="dow">{day.dow}</div><div className="dnum">{day.dnum}</div></div>
                  <div className="agenda-slots">
                    {list.length === 0 && <div className="agenda-empty">Nothing booked</div>}
                    {list.map((b) => {
                      const upcoming = new Date(`${b.date}T${b.end_time || "00:00"}:00Z`) >= now;
                      return (
                        <div className="agenda-chip" data-testid="booking-row" key={b.booking_id}>
                          <div className="chip-info">
                            <div className="ct">{b.event_title || b.purpose}</div>
                            <div className="cs">{to12h(b.start_time)} — {to12h(b.end_time)} · {b.requested_by}{b.attendees ? ` · ${b.attendees} attendees` : ""}</div>
                          </div>
                          <div className="chip-right">
                            <span className={upcoming ? "pill-up" : "pill-done"}>{upcoming && <span className="dot" />}{upcoming ? "Upcoming" : "Done"}</span>
                            <button className="chip-x" data-testid="booking-cancel-button" title="Cancel booking" onClick={() => cancel(b)}><X size={15} /></button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </section>
        </div>

        <aside className="surface new-booking" data-testid="booking-form-card">
          <h3 className="nb-title">New booking</h3>
          <form id="booking-form" onSubmit={save}>
            <div className="nb-row">
              <div className="nb-field"><label>Start</label><input data-testid="booking-start-input" className="nb-input" type="datetime-local" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} required /></div>
              <div className="nb-field"><label>End</label><input data-testid="booking-end-input" className="nb-input" type="datetime-local" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} required /></div>
            </div>
            <div className="nb-field"><label>Event / purpose title</label><input data-testid="booking-title-input" className="nb-input" placeholder="e.g. Guest lecture — AI in Industry" value={form.event_title} onChange={(e) => setForm({ ...form, event_title: e.target.value })} /></div>
            <div className="nb-row">
              <div className="nb-field"><label>Department</label><input data-testid="booking-department-input" className="nb-input" placeholder="e.g. Computer Science" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} /></div>
              <div className="nb-field"><label>Expected attendees</label><input data-testid="booking-attendees-input" className="nb-input" type="number" min="0" placeholder="0" value={form.attendees} onChange={(e) => setForm({ ...form, attendees: e.target.value })} /></div>
            </div>
            <div className="nb-field"><label>Contact (phone / email)</label><input data-testid="booking-contact-input" className="nb-input" placeholder="Who to reach for this booking" value={form.contact} onChange={(e) => setForm({ ...form, contact: e.target.value })} /></div>
            <div className="nb-field"><label>Purpose details</label><textarea data-testid="booking-purpose-input" className="nb-textarea" placeholder="Describe the reason for this reservation…" value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} required /></div>
            <button data-testid="booking-submit-button" type="submit" className="primary-btn nb-confirm" disabled={busy}>{busy ? "Confirming…" : "Confirm booking"}</button>
          </form>
        </aside>
      </div>
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
            <button data-testid="audit-close-button" className="secondary-btn compact" style={{ marginTop: 12, marginRight: 8 }} onClick={async () => { await api(`/audits/${a.audit_id}/close`, { method: "POST" }); toast.success("Audit cycle closed"); load(); }}>Close audit cycle</button>
          )}
          <button data-testid="audit-download-pdf" className="primary-btn compact" style={{ marginTop: 12 }} onClick={async () => {
            try {
              const res = await fetch(`${API}/audits/${a.audit_id}/pdf`, { credentials: "include" });
              if (!res.ok) throw new Error("Download failed");
              const blob = await res.blob();
              const url = URL.createObjectURL(blob);
              const link = document.createElement("a"); link.href = url; link.download = `audit_${a.audit_id}.pdf`;
              document.body.appendChild(link); link.click(); link.remove();
              URL.revokeObjectURL(url);
              toast.success("Audit PDF downloaded");
            } catch (e) { toast.error(e.message); }
          }}><Download size={13} /> Download PDF</button>
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

function AccessControlPanel({ users, reload }) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState([]);
  const [bulkRole, setBulkRole] = useState("Asset Manager");
  const [bulkStatus, setBulkStatus] = useState("Active");
  const [busy, setBusy] = useState(false);
  const apply = async (u, role, status) => {
    try { await api(`/admin/users/${u.user_id}/role`, { method: "PATCH", body: JSON.stringify({ role, status }) }); toast.success(`Updated ${u.name} → ${role}`); reload(); }
    catch (e) { toast.error(e.message); }
  };
  const filtered = users.filter((u) => [u.name, u.email, u.department, u.role, u.status].join(" ").toLowerCase().includes(q.toLowerCase()));
  const selectable = filtered.filter((u) => u.email !== "admin@assetflow.edu");
  const toggle = (id) => setSel((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  const allSelected = selectable.length > 0 && selectable.every((u) => sel.includes(u.user_id));
  const toggleAll = () => setSel(allSelected ? [] : selectable.map((u) => u.user_id));
  const applyBulk = async () => {
    if (sel.length === 0) return;
    setBusy(true);
    try {
      const r = await api("/admin/users/bulk-role", { method: "POST", body: JSON.stringify({ user_ids: sel, role: bulkRole, status: bulkStatus }) });
      toast.success(`${r.updated} user(s) set to ${bulkRole}${r.skipped?.length ? ` · ${r.skipped.length} skipped` : ""}`);
      setSel([]); reload();
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <section className="surface" data-testid="access-control-panel" style={{ marginTop: 16 }}>
      <div className="section-title"><div><p className="eyebrow">ACCESS CONTROL</p><h3>Set any user&rsquo;s role &amp; access</h3></div><small className="muted">{filtered.length} of {users.length} users</small></div>
      <div className="ac-search"><Search size={15} /><input data-testid="access-search-input" placeholder="Search users by name, email, department, role or status…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      {selectable.length > 0 && (
        <div className="ac-selectbar">
          <label className="ac-checkline"><input type="checkbox" data-testid="access-select-all" checked={allSelected} onChange={toggleAll} /> Select all ({selectable.length})</label>
          {sel.length > 0 && (
            <div className="ac-bulkbar" data-testid="access-bulk-bar">
              <span className="ac-selcount">{sel.length} selected</span>
              <select data-testid="access-bulk-role" value={bulkRole} onChange={(e) => setBulkRole(e.target.value)}>
                <option>Student</option><option>Employee</option><option>HOD</option><option>Asset Manager</option><option>Admin</option>
              </select>
              <select data-testid="access-bulk-status" value={bulkStatus} onChange={(e) => setBulkStatus(e.target.value)}>
                <option>Active</option><option>Pending</option><option>Suspended</option>
              </select>
              <button className="primary-btn compact" data-testid="access-bulk-apply" disabled={busy} onClick={applyBulk}>{busy ? "Applying…" : `Apply to ${sel.length}`}</button>
              <button className="link-btn" onClick={() => setSel([])}>Clear</button>
            </div>
          )}
        </div>
      )}
      <div className="ac-list">
        {filtered.length === 0 && <div className="empty">No users match &ldquo;{q}&rdquo;.</div>}
        {filtered.map((u) => {
          const isRootAdmin = u.email === "admin@assetflow.edu";
          return (
            <div className={`ac-row${sel.includes(u.user_id) ? " selected" : ""}`} data-testid="access-user-row" key={u.user_id}>
              <div className="ac-user">
                {!isRootAdmin && <input type="checkbox" data-testid="access-row-checkbox" checked={sel.includes(u.user_id)} onChange={() => toggle(u.user_id)} />}
                {isRootAdmin && <span className="ac-checkbox-spacer" />}
                <span className="avatar-sm">{initials(u.name)}</span><div><b>{u.name}</b><small>{u.email} · {u.department || "—"}</small></div>
              </div>
              <div className="ac-controls">
                <label className="ac-field"><span>Role</span>
                  <select data-testid="access-role-select" value={u.role} disabled={isRootAdmin} onChange={(e) => apply(u, e.target.value, u.status || "Active")}>
                    <option>Student</option><option>Employee</option><option>HOD</option><option>Asset Manager</option><option>Admin</option>
                  </select>
                </label>
                <label className="ac-field"><span>Status</span>
                  <select data-testid="access-status-select" value={u.status || "Active"} disabled={isRootAdmin} onChange={(e) => apply(u, u.role, e.target.value)}>
                    <option>Active</option><option>Pending</option><option>Suspended</option>
                  </select>
                </label>
              </div>
            </div>
          );
        })}
      </div>
    </section>
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
      <AccessControlPanel users={users} reload={load} />
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
      <DelegationsPanel users={users} />
      <BulkImportPanel />
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
   Delegation slots (admin only)
   ============================================================ */
function DelegationsPanel({ users }) {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ deputy_id: "", start_at: new Date().toISOString().slice(0, 16), end_at: new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 16), note: "" });
  const load = useCallback(() => api("/admin/delegations").then(setItems).catch((e) => toast.error(e.message)), []);
  useEffect(() => { load(); }, [load]);
  const create = async () => {
    if (!form.deputy_id) { toast.error("Pick a deputy"); return; }
    try {
      await api("/admin/delegations", { method: "POST", body: JSON.stringify({ ...form, start_at: new Date(form.start_at).toISOString(), end_at: new Date(form.end_at).toISOString() }) });
      toast.success("Delegation scheduled"); load();
    } catch (e) { toast.error(e.message); }
  };
  const revoke = async (d) => {
    if (!window.confirm(`Revoke delegation to ${d.deputy_name}?`)) return;
    try {
      await api(`/admin/delegations/${d.delegation_id}`, { method: "DELETE" });
      toast.success("Delegation revoked"); load();
    } catch (e) { toast.error(e.message); }
  };
  const staffOptions = users.filter((u) => u.status === "Active" && u.role !== "Admin");
  return (
    <section className="surface" data-testid="delegations-panel" style={{ marginTop: 16 }}>
      <div className="section-title"><div><p className="eyebrow">DELEGATION SLOTS</p><h3>Hand off approvals</h3></div></div>
      <p className="muted" style={{ marginBottom: 12 }}>Give a trusted deputy Admin permissions for a fixed time window — perfect when you’re travelling or on leave.</p>
      <div className="delegation-form">
        <label>Deputy
          <select data-testid="delegation-deputy" value={form.deputy_id} onChange={(e) => setForm({ ...form, deputy_id: e.target.value })}>
            <option value="">Pick a colleague…</option>
            {staffOptions.map((u) => <option key={u.user_id} value={u.user_id}>{u.name} · {u.role}</option>)}
          </select>
        </label>
        <label>Start<input data-testid="delegation-start" type="datetime-local" value={form.start_at} onChange={(e) => setForm({ ...form, start_at: e.target.value })} /></label>
        <label>End<input data-testid="delegation-end" type="datetime-local" value={form.end_at} onChange={(e) => setForm({ ...form, end_at: e.target.value })} /></label>
        <label>Note<input data-testid="delegation-note" placeholder="Reason (optional)" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
        <button data-testid="delegation-create" className="primary-btn compact" onClick={create}><Plus size={13} /> Schedule</button>
      </div>
      {items.length === 0 ? <div className="empty">No delegations scheduled.</div> : items.map((d) => (
        <div data-testid="delegation-row" className="report-row" key={d.delegation_id}>
          <div><b>{d.deputy_name}</b><small>{new Date(d.start_at).toLocaleString()} → {new Date(d.end_at).toLocaleString()}{d.note ? " · " + d.note : ""}</small></div>
          <Status>{d.status}</Status>
          {d.status !== "Revoked" && <button data-testid="delegation-revoke" className="advance-btn" style={{ width: "auto", marginTop: 0, padding: "4px 10px" }} onClick={() => revoke(d)}><X size={12} /> Revoke</button>}
        </div>
      ))}
    </section>
  );
}

/* ============================================================
   Bulk CSV import (admin only)
   ============================================================ */
function BulkImportPanel() {
  const [kind, setKind] = useState("assets");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);
  const templates = {
    assets: "name,category,location,department,tag,serial\nProjector,IT Equipment,Room 101,Computer Science,,\nLathe,Workshop Machinery,Workshop A,Mechanical,,",
    students: "name,email,roll_number,department\nMeera Nair,meera@campus.edu,CS22A45,Computer Science\nRahul Verma,rahul@campus.edu,ME22B12,Mechanical",
  };
  const copyTemplate = () => { navigator.clipboard.writeText(templates[kind]); toast.success("Template copied"); };
  const upload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) { toast.error("Pick a CSV first"); return; }
    setBusy(true); setResult(null);
    try {
      const body = await file.text();
      const res = await fetch(`${API}/admin/imports/${kind}`, { method: "POST", credentials: "include", headers: { "Content-Type": "text/csv" }, body });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Import failed");
      setResult(data);
      toast.success(`Imported ${data.created} · skipped ${data.skipped}`);
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <section className="surface" data-testid="bulk-import-panel" style={{ marginTop: 16 }}>
      <div className="section-title"><div><p className="eyebrow">BULK IMPORT</p><h3>Drop a CSV to onboard many at once</h3></div><button data-testid="bulk-copy-template" className="link-btn" onClick={copyTemplate}>Copy template <ArrowRight size={12} /></button></div>
      <div className="inline-form" style={{ marginBottom: 10 }}>
        <select data-testid="bulk-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="assets">Assets</option>
          <option value="students">Students</option>
        </select>
        <input data-testid="bulk-file" ref={fileRef} type="file" accept=".csv,text/csv" />
        <button data-testid="bulk-upload" className="primary-btn compact" disabled={busy} onClick={upload}><Upload size={13} /> {busy ? "Uploading…" : "Import"}</button>
      </div>
      {result && (
        <div className="bulk-result" data-testid="bulk-result">
          <p className="eyebrow">Result · {result.created} created · {result.skipped} skipped</p>
          {result.rows.slice(0, 30).map((r) => (
            <div className="simple-row" key={r.row} data-testid="bulk-result-row">
              <b>Row {r.row}: {r.status}</b>
              <small>{r.message || r.name || r.asset_id || r.user_id || ""}</small>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ============================================================
   Router
   ============================================================ */
function ProtectedApp() {
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

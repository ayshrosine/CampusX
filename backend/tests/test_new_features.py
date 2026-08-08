"""Tests for iteration 3 features: notifications, report downloads, role preview,
asset by tag, and blank/whitespace field validators."""
import os, uuid, requests, pytest

BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')


@pytest.fixture(scope='module')
def admin():
    s = requests.Session()
    r = s.post(BASE + '/api/auth/login', json={'email': 'admin@assetflow.edu', 'password': 'Admin123!'})
    assert r.status_code == 200
    return s


@pytest.fixture(scope='module')
def demo():
    s = requests.Session()
    r = s.post(BASE + '/api/auth/login', json={'email': 'demo@assetflow.edu', 'password': 'Campus123!'})
    assert r.status_code == 200
    return s


# ---------- Notifications ----------
class TestNotifications:
    def test_get_notifications_shape(self, admin):
        r = admin.get(BASE + '/api/notifications')
        assert r.status_code == 200
        data = r.json()
        assert 'items' in data and 'unread' in data and 'last_seen' in data
        assert isinstance(data['items'], list)
        assert isinstance(data['unread'], int)
        for it in data['items']:
            assert {'id', 'kind', 'title', 'detail', 'when', 'link'} <= set(it.keys())

    def test_mark_all_read_zeros_unread(self, admin):
        r = admin.post(BASE + '/api/notifications/mark-all-read')
        assert r.status_code == 200 and r.json().get('ok') is True
        after = admin.get(BASE + '/api/notifications').json()
        assert after['unread'] == 0

    def test_notifications_requires_auth(self):
        r = requests.get(BASE + '/api/notifications')
        assert r.status_code == 401


# ---------- Report downloads ----------
class TestReportDownloads:
    def test_csv_download(self, admin):
        r = admin.get(BASE + '/api/reports/accreditation/download', params={'format': 'csv'})
        assert r.status_code == 200
        assert 'text/csv' in r.headers.get('content-type', '')
        body = r.content.decode()
        assert 'Metric,Value' in body or body.startswith('Metric')
        assert 'Total tracked assets' in body
        assert len(body) > 100

    def test_pdf_download(self, admin):
        r = admin.get(BASE + '/api/reports/accreditation/download', params={'format': 'pdf'})
        assert r.status_code == 200
        assert 'application/pdf' in r.headers.get('content-type', '')
        assert r.content[:4] == b'%PDF'
        assert len(r.content) > 500

    def test_bad_format_rejected(self, admin):
        r = admin.get(BASE + '/api/reports/accreditation/download', params={'format': 'xml'})
        assert r.status_code == 400


# ---------- Role preview ----------
class TestRolePreview:
    @pytest.mark.parametrize('role', ['Student', 'Employee', 'HOD', 'Asset Manager', 'Admin'])
    def test_role_preview_admin(self, admin, role):
        r = admin.get(f'{BASE}/api/admin/role-preview/{role}')
        assert r.status_code == 200
        d = r.json()
        assert d['role'] == role
        assert isinstance(d['permissions'], list)
        assert isinstance(d['capabilities'], list)
        assert isinstance(d['visible_pages'], list) and d['visible_pages']

    def test_unknown_role(self, admin):
        r = admin.get(BASE + '/api/admin/role-preview/Nobody')
        assert r.status_code == 400

    def test_non_admin_forbidden(self, demo):
        r = demo.get(BASE + '/api/admin/role-preview/Student')
        assert r.status_code == 403


# ---------- Asset by tag ----------
class TestAssetByTag:
    def test_lookup_seed_tag(self, demo):
        # Find a real seeded tag
        assets = demo.get(BASE + '/api/assets').json()
        assert assets
        tag = assets[0]['tag']
        r = demo.get(f'{BASE}/api/assets/by-tag/{tag}')
        assert r.status_code == 200
        assert r.json()['tag'] == tag

    def test_lookup_missing_tag(self, demo):
        r = demo.get(BASE + '/api/assets/by-tag/AF-9999-DOES-NOT-EXIST')
        assert r.status_code == 404


# ---------- Validators ----------
class TestValidators:
    @pytest.mark.parametrize('bad', ['', '   ', 'a', ' a '])
    def test_department_rejects_blank(self, admin, bad):
        r = admin.post(BASE + '/api/admin/departments', json={'name': bad})
        assert r.status_code == 422, f'expected 422 got {r.status_code}: {r.text}'

    @pytest.mark.parametrize('bad', ['', '   ', 'a', ' a '])
    def test_category_rejects_blank(self, admin, bad):
        r = admin.post(BASE + '/api/admin/categories', json={'name': bad})
        assert r.status_code == 422, f'expected 422 got {r.status_code}: {r.text}'

    def test_valid_trimmed_department_creates_and_logs(self, admin):
        suffix = 'TEST_NEW_' + uuid.uuid4().hex[:6]
        r = admin.post(BASE + '/api/admin/departments', json={'name': '  ' + suffix + '  '})
        assert r.status_code == 200
        assert r.json()['name'] == suffix  # stripped
        # Activity was logged
        acts = admin.get(BASE + '/api/activity').json()
        assert any(a.get('action') == 'department created' and a.get('after', {}).get('name') == suffix for a in acts)

    def test_valid_trimmed_category_creates(self, admin):
        suffix = 'TEST_NEW_' + uuid.uuid4().hex[:6]
        r = admin.post(BASE + '/api/admin/categories', json={'name': '  ' + suffix + '  '})
        assert r.status_code == 200
        assert r.json()['name'] == suffix

    def test_booking_rejects_blank_purpose(self, admin):
        b = {'resource_id': 'ast_seed_1', 'date': '2099-02-01', 'start_time': '09:00', 'end_time': '10:00', 'purpose': '   '}
        r = admin.post(BASE + '/api/bookings', json=b)
        assert r.status_code == 422

    def test_audit_rejects_blank(self, admin):
        r = admin.post(BASE + '/api/audits', json={'department': '  ', 'period': 'x', 'auditors': []})
        assert r.status_code == 422

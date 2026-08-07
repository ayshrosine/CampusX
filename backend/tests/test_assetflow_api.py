import os, requests, pytest
BASE=os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
@pytest.fixture(scope='session')
def client():
    s=requests.Session(); r=s.post(BASE+'/api/auth/login',json={'email':'demo@assetflow.edu','password':'Campus123!'})
    assert r.status_code==200 and r.json()['email']=='demo@assetflow.edu'
    return s

def test_protected_and_dashboard(client):
    r=client.get(BASE+'/api/dashboard'); assert r.status_code==200; d=r.json(); assert d['kpis']['total_assets']>=1; assert isinstance(d['activity'],list)
def test_inventory_filters(client):
    r=client.get(BASE+'/api/assets',params={'status':'Available'}); assert r.status_code==200
    assert all(a['status']=='Available' for a in r.json())
def test_asset_checkout_checkin_activity(client):
    assets=client.get(BASE+'/api/assets',params={'status':'Available'}).json(); assert assets
    aid=assets[0]['asset_id']; r=client.post(f'{BASE}/api/assets/{aid}/checkout',json={'holder':'TEST_API Holder'}); assert r.status_code==200; assert r.json()['status']=='Allocated'
    r=client.post(f'{BASE}/api/assets/{aid}/checkin'); assert r.status_code==200; assert r.json()['status']=='Available'
    hist=client.get(f'{BASE}/api/assets/{aid}'); assert hist.status_code==200; actions=[x['action'] for x in hist.json()['history']]; assert 'asset checked out' in actions and 'asset checked in' in actions
def test_create_maintenance_and_advance(client):
    aid=client.get(BASE+'/api/assets').json()[0]['asset_id']; r=client.post(BASE+'/api/maintenance',json={'asset_id':aid,'description':'TEST_API inspection','priority':'Low'}); assert r.status_code==200; mid=r.json()['request_id']; assert r.json()['status']=='Pending'
    r=client.patch(f'{BASE}/api/maintenance/{mid}',json={'status':'Approved'}); assert r.status_code==200; assert r.json()['status']=='Approved'
    items=client.get(BASE+'/api/maintenance').json(); assert any(x['request_id']==mid and x['status']=='Approved' for x in items)
def test_reports_activity(client):
    r=client.get(BASE+'/api/reports'); assert r.status_code==200; assert 'departments' in r.json()
    r=client.get(BASE+'/api/activity'); assert r.status_code==200; assert any(x['action']=='asset checked out' for x in r.json())
def test_unauthenticated_rejected():
    r=requests.get(BASE+'/api/dashboard'); assert r.status_code==401



def test_admin_rbac_and_modules():
    admin=requests.Session(); assert admin.post(BASE+'/api/auth/login',json={'email':'admin@assetflow.edu','password':'Admin123!'}).status_code==200
    nonadmin=requests.Session(); assert nonadmin.post(BASE+'/api/auth/login',json={'email':'demo@assetflow.edu','password':'Campus123!'}).status_code==200
    assert nonadmin.get(BASE+'/api/admin/users').status_code==403
    suffix='TEST_MODULE_'+__import__('uuid').uuid4().hex[:6]
    assert admin.post(BASE+'/api/admin/departments',json={'name':suffix}).status_code==200
    assert admin.post(BASE+'/api/admin/categories',json={'name':suffix}).status_code==200
    b={'resource_id':'ast_seed_1','date':'2099-01-01','start_time':'10:00','end_time':'11:00','purpose':suffix}
    first=admin.post(BASE+'/api/bookings',json=b); assert first.status_code==200
    assert admin.post(BASE+'/api/bookings',json=b).status_code==409
    bid=first.json()['booking_id']; assert admin.delete(BASE+'/api/bookings/'+bid).status_code==200
    audit=admin.post(BASE+'/api/audits',json={'department':'Computer Science','period':suffix,'auditors':['Rohan Kapoor']}); assert audit.status_code==200
    aid=audit.json()['audit_id']; assert admin.post(BASE+f'/api/audits/{aid}/close').status_code==200
    nodues=admin.get(BASE+'/api/nodues'); assert nodues.status_code==200 and nodues.json()
    assert admin.get(BASE+'/api/reports/accreditation').json()['format']=='NAAC/NBA-ready'
    activity=admin.get(BASE+'/api/activity'); assert activity.status_code==200 and any(x.get('action')=='booking created' for x in activity.json())

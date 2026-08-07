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

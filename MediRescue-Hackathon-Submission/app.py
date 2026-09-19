from flask import Flask, request, jsonify, render_template, session
import sqlite3, math, os, secrets
import flask
from werkzeug.security import generate_password_hash, check_password_hash
from aws_services import mirror_emergency, notify_critical_emergency, calculate_route_eta
from flask_cors import CORS

app = Flask(__name__)
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": ["http://127.0.0.1:5000", "http://localhost:5000", "http://127.0.0.1:5500", "http://localhost:5500"]
        }
    },
    supports_credentials=True
)
app.secret_key = os.environ.get('MEDIRESCUE_SECRET', secrets.token_hex(32))
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'medirescue.db')

STATUSES_ACTIVE = ('HOSPITAL_BROADCAST','HOSPITAL_ACCEPTED','DISPATCHED','PICKED_UP')
STATE_TRANSITIONS = {
    'PENDING_CONFIRMATION': {'HOSPITAL_BROADCAST','CANCELLED'},
    'HOSPITAL_BROADCAST': {'HOSPITAL_ACCEPTED','NO_HOSPITAL'},
    'HOSPITAL_ACCEPTED': {'DISPATCHED'},
    'DISPATCHED': {'PICKED_UP'},
    'PICKED_UP': {'COMPLETED'},
    'COMPLETED': set(),
}

def transition(c, eid, target, event_type, message):
    e=c.execute('SELECT status FROM emergencies WHERE id=?',(eid,)).fetchone()
    if not e or target not in STATE_TRANSITIONS.get(e['status'], set()):
        return False, e['status'] if e else None
    c.execute('UPDATE emergencies SET status=? WHERE id=? AND status=?',(target,eid,e['status']))
    if c.execute('SELECT changes()').fetchone()[0] != 1:
        return False, e['status']
    log_event(c,eid,event_type,message)
    return True, target

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL, phone TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, age INTEGER, blood_group TEXT,
      address TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS contacts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
      name TEXT NOT NULL, phone TEXT NOT NULL, relationship TEXT,
      FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS hospitals(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
      phone TEXT NOT NULL, emergency_phone TEXT, address TEXT,
      latitude REAL NOT NULL, longitude REAL NOT NULL,
      capacity INTEGER DEFAULT 20, occupied INTEGER DEFAULT 0,
      emergency_available INTEGER DEFAULT 1, status TEXT DEFAULT 'ONLINE',
      username TEXT UNIQUE, password_hash TEXT, verified INTEGER DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS drivers(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
      phone TEXT NOT NULL, license_number TEXT, ambulance_number TEXT NOT NULL,
      hospital_id INTEGER, latitude REAL, longitude REAL,
      status TEXT DEFAULT 'OFFLINE', username TEXT UNIQUE,
      password_hash TEXT, verified INTEGER DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS emergencies(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
      guest_name TEXT, guest_phone TEXT,
      latitude REAL NOT NULL, longitude REAL NOT NULL, accuracy REAL,
      status TEXT DEFAULT 'PENDING_CONFIRMATION',
      hospital_id INTEGER, ambulance_id INTEGER,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      accepted_at DATETIME, completed_at DATETIME);
    CREATE TABLE IF NOT EXISTS emergency_hospitals(
      id INTEGER PRIMARY KEY AUTOINCREMENT, emergency_id INTEGER,
      hospital_id INTEGER, status TEXT DEFAULT 'WAITING',
      priority_rank INTEGER DEFAULT 999,
      notified_at DATETIME, responded_at DATETIME,
      UNIQUE(emergency_id,hospital_id));
    CREATE TABLE IF NOT EXISTS locations(
      id INTEGER PRIMARY KEY AUTOINCREMENT, emergency_id INTEGER,
      driver_id INTEGER, latitude REAL NOT NULL, longitude REAL NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS emergency_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT, emergency_id INTEGER NOT NULL,
      event_type TEXT NOT NULL, message TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    ''')
    # Lightweight migrations for databases created by earlier MediRescue versions.
    cols=[r['name'] for r in c.execute('PRAGMA table_info(emergencies)').fetchall()]
    if 'priority' not in cols: c.execute("ALTER TABLE emergencies ADD COLUMN priority TEXT DEFAULT 'HIGH'")
    eh_cols=[r['name'] for r in c.execute('PRAGMA table_info(emergency_hospitals)').fetchall()]
    if 'priority_rank' not in eh_cols: c.execute("ALTER TABLE emergency_hospitals ADD COLUMN priority_rank INTEGER DEFAULT 999")
    if 'notified_at' not in eh_cols: c.execute("ALTER TABLE emergency_hospitals ADD COLUMN notified_at DATETIME")
    if 'responded_at' not in eh_cols: c.execute("ALTER TABLE emergency_hospitals ADD COLUMN responded_at DATETIME")
    c.execute("CREATE INDEX IF NOT EXISTS idx_emergency_events_eid ON emergency_events(emergency_id, id)")
    # Demo accounts only for hackathon testing.
    if c.execute('SELECT COUNT(*) FROM hospitals').fetchone()[0] == 0:
        c.execute('''INSERT INTO hospitals
        (name,phone,emergency_phone,address,latitude,longitude,capacity,occupied,
         emergency_available,status,username,password_hash,verified)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)''',
        ('MediRescue Demo Hospital','9999999999','108','Demo Location',
         28.9845,77.7064,20,0,1,'ONLINE','demo_hospital',
         generate_password_hash('hospital123')))
    if c.execute('SELECT COUNT(*) FROM drivers').fetchone()[0] == 0:
        h=c.execute('SELECT id FROM hospitals LIMIT 1').fetchone()['id']
        c.execute('''INSERT INTO drivers
        (name,phone,license_number,ambulance_number,hospital_id,latitude,longitude,
         status,username,password_hash,verified)
        VALUES (?,?,?,?,?,?,?,?,?,?,1)''',
        ('Demo Driver','8888888888','DL-DEMO-001','MR-AMB-01',h,
         28.9845,77.7064,'AVAILABLE','demo_driver',
         generate_password_hash('driver123')))
    c.commit(); c.close()

def dist(a,b,c,d):
    R=6371
    p1,p2=math.radians(a),math.radians(c)
    dp=math.radians(c-a); dl=math.radians(d-b)
    x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R*2*math.atan2(math.sqrt(x),math.sqrt(1-x))

def eta_minutes(km, speed_kmh=35):
    try: return max(1, round((float(km) / max(10, float(speed_kmh))) * 60))
    except Exception: return None


def clean(v):
    return None if v in ('',None) else v

def log_event(c, eid, event_type, message):
    c.execute('INSERT INTO emergency_events(emergency_id,event_type,message) VALUES(?,?,?)',(eid,event_type,message))

def priority_label(value):
    return value if value in ('CRITICAL','HIGH','NORMAL') else 'HIGH'
@app.route("/health", methods=["GET"])
def health():
    return {
        "success": True,
        "status": "ok",
        "message": "MediRescue backend is running"
    }, 200
@app.route(
    "/api/emergency/<int:emergency_id>/patient-location",
    methods=["POST"]
)
def update_patient_location(emergency_id):
    data = request.get_json(silent=True) or {}

    latitude = data.get("latitude")
    longitude = data.get("longitude")
    accuracy = data.get("accuracy")

    if latitude is None or longitude is None:
        return {
            "success": False,
            "message": "Latitude and longitude are required."
        }, 400

    # Yahan apni database update logic lagao.
    # Example:
    # UPDATE emergencies
    # SET latitude=?, longitude=?
    # WHERE id=?

    return {
        "success": True,
        "message": "Patient location updated.",
        "emergency_id": emergency_id,
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": accuracy
    }, 200

@app.route('/')
def patient(): return render_template('patient.html')
@app.route('/hospital')
def hospital():
    if not session.get('hospital_id'):
        return render_template('hospital.html')
    return render_template('hospital.html')
@app.route('/driver')
def driver():
    if not session.get('driver_id'):
        return render_template('driver.html')
    return render_template('driver.html')
@app.route('/admin')
def admin(): return render_template('admin.html')

# ---------------- PATIENT ----------------
@app.post('/api/signup')
def signup():
    d=flask.request.json or {}
    if not d.get('name') or not d.get('phone') or not d.get('password'):
        return jsonify(success=False,message='Name, phone and password required'),400
    c=db()
    try:
        cur=c.execute('''INSERT INTO users(name,phone,password_hash,age,blood_group,address)
        VALUES(?,?,?,?,?,?)''',(d['name'],d['phone'],generate_password_hash(d['password']),
        clean(d.get('age')),clean(d.get('blood_group')),clean(d.get('address'))))
        uid=cur.lastrowid
        if d.get('contact_name') and d.get('contact_phone'):
            c.execute('''INSERT INTO contacts(user_id,name,phone,relationship) VALUES(?,?,?,?)''',
                      (uid,d['contact_name'],d['contact_phone'],d.get('relationship','')))
        c.commit(); session['user_id']=uid
        return jsonify(success=True,user_id=uid)
    except sqlite3.IntegrityError:
        return jsonify(success=False,message='Phone already registered'),409
    finally: c.close()

@app.post('/api/login')
def login():
    d=flask.request.json or {}; c=db(); u=c.execute('SELECT * FROM users WHERE phone=?',(d.get('phone',''),)).fetchone(); c.close()
    if not u or not check_password_hash(u['password_hash'],d.get('password','')):
        return jsonify(success=False,message='Invalid login'),401
    session['user_id']=u['id']; return jsonify(success=True,user=dict(u))

@app.get('/api/me')
def me():
    uid=session.get('user_id')
    if not uid: return jsonify(success=False,logged_in=False)
    c=db(); u=c.execute('SELECT id,name,phone,age,blood_group,address FROM users WHERE id=?',(uid,)).fetchone(); c.close()
    return jsonify(success=bool(u),logged_in=bool(u),user=dict(u) if u else None)

@app.post('/api/logout')
def logout(): session.clear(); return jsonify(success=True)

@app.post('/api/sos/start')
def sos_start():
    d=flask.request.json or {}
    try:
        lat=float(d['latitude']); lon=float(d['longitude']); acc=float(d.get('accuracy') or 0)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180): raise ValueError('out of range')
        if acc < 0: acc=0
    except: return jsonify(success=False,message='Valid current GPS location required'),400
    uid=session.get('user_id'); guest_name=None; guest_phone=None
    # SOS is intentionally available without login: this supports bystanders and patients in crisis.
    if not uid:
        guest_name='Bystander / Guest'
        guest_phone=None
    c=db()
    cur=c.execute('''INSERT INTO emergencies(user_id,guest_name,guest_phone,latitude,longitude,accuracy,status)
                     VALUES(?,?,?,?,?,?,?)''',(uid,guest_name,guest_phone,lat,lon,acc,'PENDING_CONFIRMATION'))
    eid=cur.lastrowid
    log_event(c,eid,'SOS_CREATED','SOS received; safety countdown started.')

    # Safety window: create the emergency first, but do NOT notify hospitals until the 5-second countdown completes.
    c.commit(); c.close(); session['active_emergency']=eid
    aws = mirror_emergency(eid, {
        'event_type':'SOS_CREATED', 'latitude':lat, 'longitude':lon,
        'accuracy':acc, 'status':'PENDING_CONFIRMATION',
        'source':'patient' if uid else 'bystander'
    })
    return jsonify(success=True,emergency_id=eid,status='PENDING_CONFIRMATION',aws=aws,
                   message='SOS detected. You have 5 seconds to cancel if this was accidental.')

@app.post('/api/emergency/<int:emergency_id>/patient-location')
def patient_location(emergency_id):
    d = flask.request.json or {}

    try:
        lat = float(d['latitude'])
        lon = float(d['longitude'])
        acc = float(d.get('accuracy') or 0)

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError('out of range')

        if acc < 0:
            acc = 0

    except (KeyError, TypeError, ValueError):
        return jsonify(
            success=False,
            message='Valid GPS location required'
        ), 400

    c = db()

    emergency = c.execute(
        'SELECT id FROM emergencies WHERE id=?',
        (emergency_id,)
    ).fetchone()

    if not emergency:
        c.close()
        return jsonify(
            success=False,
            message='Emergency not found'
        ), 404

    # Latest patient GPS ko emergency record mein update karo
    c.execute(
        '''
        UPDATE emergencies
        SET latitude=?, longitude=?, accuracy=?
        WHERE id=?
        ''',
        (lat, lon, acc, emergency_id)
    )

    log_event(
        c,
        emergency_id,
        'PATIENT_LOCATION_UPDATED',
        f'Patient GPS updated: {lat}, {lon}, accuracy={acc}'
    )

    c.commit()
    c.close()

    return jsonify(
        success=True,
        emergency_id=emergency_id,
        latitude=lat,
        longitude=lon,
        accuracy=acc,
        message='Patient location updated'
    ), 200

@app.post('/api/sos/cancel')
def sos_cancel():
    eid=(flask.request.json or {}).get('emergency_id'); c=db()
    cur=c.execute("UPDATE emergencies SET status='CANCELLED' WHERE id=? AND status='PENDING_CONFIRMATION'",(eid,))
    changed=cur.rowcount > 0
    c.commit(); c.close()
    if changed:
        c=db(); log_event(c,eid,'SOS_CANCELLED','Emergency cancelled during the safety window.'); c.commit(); c.close()
        mirror_emergency(eid, {'event_type':'SOS_CANCELLED','status':'CANCELLED'})
        return jsonify(success=True,message='Emergency cancelled before hospital notification.')
    return jsonify(success=False,message='Emergency can no longer be cancelled.'),409

@app.post('/api/sos/confirm')
def sos_confirm():
    eid=(flask.request.json or {}).get('emergency_id'); c=db()
    e=c.execute('SELECT * FROM emergencies WHERE id=?',(eid,)).fetchone()
    if not e: c.close(); return jsonify(success=False,message='Emergency not found'),404
    if e['status']=='HOSPITAL_BROADCAST':
        rows=c.execute("SELECT h.id,h.name,eh.status,eh.priority_rank FROM emergency_hospitals eh JOIN hospitals h ON h.id=eh.hospital_id WHERE eh.emergency_id=? ORDER BY eh.priority_rank",(eid,)).fetchall()
        c.close(); return jsonify(success=True,emergency_id=eid,status='HOSPITAL_BROADCAST',hospitals=[dict(r) for r in rows],message='Emergency already broadcast')
    if e['status']!='PENDING_CONFIRMATION': c.close(); return jsonify(success=False,message='Emergency is not pending'),400
    hs=c.execute('''SELECT * FROM hospitals WHERE verified=1 AND status='ONLINE'
                    AND emergency_available=1 AND (capacity=0 OR occupied<capacity)''').fetchall()
    if not hs:
        c.execute("UPDATE emergencies SET status='NO_HOSPITAL' WHERE id=?",(eid,)); c.commit(); c.close()
        return jsonify(success=False,message='No available hospital found')

    # Intelligent matching: nearest hospital is rank 1. Capacity headroom only breaks ties.
    candidates=[]
    for h in hs:
        km=dist(e['latitude'],e['longitude'],h['latitude'],h['longitude'])
        headroom=1.0 if h['capacity']==0 else max(0.0,min(1.0,(h['capacity']-h['occupied'])/max(1,h['capacity'])))
        candidates.append((km, headroom, h))
    ranked=sorted(candidates, key=lambda x:(x[0], -x[1]))

    for rank,(km,headroom,h) in enumerate(ranked, start=1):
        status='PENDING' if rank==1 else 'WAITING'
        c.execute("INSERT OR IGNORE INTO emergency_hospitals(emergency_id,hospital_id,status,priority_rank,notified_at) VALUES(?,?,?,?,CASE WHEN ?='PENDING' THEN CURRENT_TIMESTAMP ELSE NULL END)",(eid,h['id'],status,rank,status))
        c.execute("UPDATE emergency_hospitals SET priority_rank=?, status=CASE WHEN ?=1 THEN 'PENDING' ELSE status END, notified_at=CASE WHEN ?=1 THEN COALESCE(notified_at,CURRENT_TIMESTAMP) ELSE notified_at END WHERE emergency_id=? AND hospital_id=?",(rank,1 if rank==1 else 0,1 if rank==1 else 0,eid,h['id']))

    ok, _ = transition(c,eid,'HOSPITAL_BROADCAST','HOSPITAL_BROADCAST',f'Nearest hospital prioritized; {len(ranked)} suitable hospitals ranked.')
    if not ok:
        c.rollback(); c.close(); return jsonify(success=False,message='Emergency state changed; please refresh'),409
    c.execute("UPDATE emergencies SET priority=? WHERE id=?",('HIGH',eid)); c.commit(); c.close()

    nearest_km, _, nearest=ranked[0]
    hospital_list=[{'id':h['id'],'name':h['name'],'distance_km':round(km,2),'priority_rank':rank,'notification_status':'NOTIFIED' if rank==1 else 'WAITING'} for rank,(km,_,h) in enumerate(ranked,start=1)]
    aws = mirror_emergency(eid, {'event_type':'HOSPITAL_BROADCAST','status':'HOSPITAL_BROADCAST','latitude':e['latitude'],'longitude':e['longitude'],'hospital_count':len(hospital_list),'priority_hospital_id':nearest['id'],'priority_hospital_name':nearest['name'],'priority_hospital_distance_km':round(nearest_km,2)})
    notification=notify_critical_emergency({
        'emergency_id': eid,
        'latitude': e['latitude'],
        'longitude': e['longitude'],
        'accuracy': e['accuracy'],
        'priority_hospital_id': nearest['id'],
        'priority_hospital_name': nearest['name'],
        'priority_hospital_distance_km': round(nearest_km, 2),
        'message': f'New critical emergency. Nearest verified hospital prioritized: {nearest["name"]} ({nearest_km:.2f} km).',
    })
    return jsonify(success=True,emergency_id=eid,hospitals=hospital_list,aws=aws,notification=notification,priority_hospital={'id':nearest['id'],'name':nearest['name'],'distance_km':round(nearest_km,2)})

@app.get('/api/emergency/<int:eid>')
def emergency_status(eid):
    c=db(); r=c.execute('''SELECT e.*,u.name patient_name,u.phone patient_phone,u.age,u.blood_group,
        h.name hospital_name,h.phone hospital_phone,h.latitude hospital_latitude,h.longitude hospital_longitude,
        d.id driver_id,d.name driver_name,d.phone driver_phone,d.ambulance_number,
        d.latitude ambulance_latitude,d.longitude ambulance_longitude
        FROM emergencies e LEFT JOIN users u ON u.id=e.user_id
        LEFT JOIN hospitals h ON h.id=e.hospital_id LEFT JOIN drivers d ON d.id=e.ambulance_id WHERE e.id=?''',(eid,)).fetchone(); c.close()
    if not r:return jsonify(success=False),404
    return jsonify(success=True,emergency=dict(r))


# ---------------- PHASE 4: TRACKING / HISTORY ----------------
@app.get('/api/emergency/<int:eid>/timeline')
def emergency_timeline(eid):
    c=db(); e=c.execute('SELECT * FROM emergencies WHERE id=?',(eid,)).fetchone()
    if not e: c.close(); return jsonify(success=False,message='Emergency not found'),404
    rows=c.execute('SELECT event_type,message,created_at FROM emergency_events WHERE emergency_id=? ORDER BY id',(eid,)).fetchall()
    c.close(); return jsonify(success=True,timeline=[dict(r) for r in rows])

@app.get('/api/patient/emergencies')
def patient_history():
    uid=session.get('user_id')
    if not uid:return jsonify(success=False,message='Login required'),401
    c=db(); rows=c.execute("""SELECT e.id,e.status,e.latitude,e.longitude,e.created_at,e.accepted_at,
        h.name hospital_name,d.name driver_name,d.ambulance_number FROM emergencies e
        LEFT JOIN hospitals h ON h.id=e.hospital_id LEFT JOIN drivers d ON d.id=e.ambulance_id
        WHERE e.user_id=? ORDER BY e.id DESC LIMIT 20""",(uid,)).fetchall(); c.close()
    return jsonify(success=True,emergencies=[dict(r) for r in rows])

@app.get('/api/emergency/<int:eid>/eta')
def emergency_eta(eid):
    c=db(); e=c.execute("""SELECT e.latitude patient_latitude,e.longitude patient_longitude,
        h.latitude hospital_latitude,h.longitude hospital_longitude,
        d.latitude driver_latitude,d.longitude driver_longitude,d.status driver_status
        FROM emergencies e LEFT JOIN hospitals h ON h.id=e.hospital_id LEFT JOIN drivers d ON d.id=e.ambulance_id
        WHERE e.id=?""",(eid,)).fetchone(); c.close()
    if not e:return jsonify(success=False,message='Emergency not found'),404
    out={'success':True,'to_patient':None,'to_hospital':None}
    if e['driver_latitude'] is not None:
        if e['patient_latitude'] is not None:
            route=calculate_route_eta(e['driver_latitude'],e['driver_longitude'],e['patient_latitude'],e['patient_longitude'])
            if route: out['to_patient']=route
            else:
                km=dist(e['driver_latitude'],e['driver_longitude'],e['patient_latitude'],e['patient_longitude'])
                out['to_patient']={'distance_km':round(km,2),'eta_minutes':eta_minutes(km),'source':'haversine_fallback'}
        if e['hospital_latitude'] is not None:
            route=calculate_route_eta(e['driver_latitude'],e['driver_longitude'],e['hospital_latitude'],e['hospital_longitude'])
            if route: out['to_hospital']=route
            else:
                km=dist(e['driver_latitude'],e['driver_longitude'],e['hospital_latitude'],e['hospital_longitude'])
                out['to_hospital']={'distance_km':round(km,2),'eta_minutes':eta_minutes(km),'source':'haversine_fallback'}
    return jsonify(**out)

@app.get('/api/hospital/summary')
def hospital_summary():
    hid=session.get('hospital_id')
    if not hid:return jsonify(success=False,message='Hospital login required'),401
    c=db(); h=c.execute('SELECT id,name,capacity,occupied,status,emergency_available,latitude,longitude FROM hospitals WHERE id=?',(hid,)).fetchone()
    stats=c.execute("""SELECT COUNT(*) total,
        SUM(CASE WHEN e.status='HOSPITAL_BROADCAST' THEN 1 ELSE 0 END) pending,
        SUM(CASE WHEN e.status='HOSPITAL_ACCEPTED' THEN 1 ELSE 0 END) accepted
        FROM emergency_hospitals eh JOIN emergencies e ON e.id=eh.emergency_id WHERE eh.hospital_id=?""",(hid,)).fetchone(); c.close()
    return jsonify(success=bool(h),hospital=dict(h) if h else None,stats=dict(stats) if stats else {})

# ---------------- HOSPITAL ----------------
@app.post('/api/hospital/register')
def hospital_register():
    d=flask.request.json or {}
    required=['name','phone','address','latitude','longitude','username','password']
    if any(not d.get(k) for k in required): return jsonify(success=False,message='All required hospital fields must be filled'),400
    c=db()
    try:
        cur=c.execute('''INSERT INTO hospitals(name,phone,emergency_phone,address,latitude,longitude,capacity,
          emergency_available,status,username,password_hash,verified) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0)''',
          (d['name'],d['phone'],d.get('emergency_phone'),d['address'],float(d['latitude']),float(d['longitude']),int(d.get('capacity') or 20),1,'ONLINE',d['username'],generate_password_hash(d['password'])))
        c.commit(); return jsonify(success=True,message='Registration submitted. Admin verification is required.',hospital_id=cur.lastrowid)
    except sqlite3.IntegrityError:return jsonify(success=False,message='Hospital username already exists'),409
    except Exception as ex:return jsonify(success=False,message=str(ex)),400
    finally:c.close()

@app.post('/api/hospital/login')
def hlogin():
    d=flask.request.json or {}; c=db(); h=c.execute('SELECT * FROM hospitals WHERE username=?',(d.get('username',''),)).fetchone(); c.close()
    if not h or not h['verified'] or not check_password_hash(h['password_hash'],d.get('password','')):
        return jsonify(success=False,message='Invalid or unverified hospital login'),401
    session['hospital_id']=h['id']; return jsonify(success=True,hospital=dict(h))

@app.get('/api/hospital/me')
def hme():
    hid=session.get('hospital_id'); c=db(); h=c.execute('SELECT * FROM hospitals WHERE id=?',(hid,)).fetchone() if hid else None; c.close()
    return jsonify(success=bool(h),hospital=dict(h) if h else None)

@app.post('/api/hospital/settings')
def hsettings():
    hid=session.get('hospital_id'); d=flask.request.json or {}
    if not hid:return jsonify(success=False,message='Hospital login required'),401
    c=db(); c.execute('''UPDATE hospitals SET emergency_available=?,status=?,capacity=?,occupied=?,latitude=COALESCE(?,latitude),longitude=COALESCE(?,longitude) WHERE id=?''',
                      (int(bool(d.get('emergency_available',1))),d.get('status','ONLINE'),int(d.get('capacity',20)),int(d.get('occupied',0)),clean(d.get('latitude')),clean(d.get('longitude')),hid)); c.commit(); c.close(); return jsonify(success=True)

@app.get('/api/hospital/emergencies')
def h_emergencies():
    hid=session.get('hospital_id')
    if not hid:return jsonify(success=False,message='Hospital login required'),401
    c=db()
    # If the current priority hospital does not respond for 30 seconds, notify the next-nearest.
    stale=c.execute("SELECT eh.emergency_id,eh.priority_rank FROM emergency_hospitals eh JOIN emergencies e ON e.id=eh.emergency_id WHERE eh.status='PENDING' AND e.status='HOSPITAL_BROADCAST' AND eh.notified_at IS NOT NULL AND (julianday('now')-julianday(eh.notified_at))*86400 >= 30").fetchall()
    for row in stale:
        nxt=c.execute("SELECT id,hospital_id,priority_rank FROM emergency_hospitals WHERE emergency_id=? AND status='WAITING' ORDER BY priority_rank LIMIT 1",(row['emergency_id'],)).fetchone()
        if nxt:
            c.execute("UPDATE emergency_hospitals SET status='EXPIRED',responded_at=CURRENT_TIMESTAMP WHERE emergency_id=? AND status='PENDING'",(row['emergency_id'],))
            c.execute("UPDATE emergency_hospitals SET status='PENDING',notified_at=CURRENT_TIMESTAMP WHERE id=?",(nxt['id'],))
            log_event(c,row['emergency_id'],'HOSPITAL_ESCALATED',f'No response from priority hospital; escalated to hospital rank {nxt["priority_rank"]}.')
    c.commit()
    rows=c.execute("SELECT e.*,u.name patient_name,u.phone patient_phone,u.age patient_age,u.blood_group patient_blood,eh.status hospital_response,eh.priority_rank,h.name target_hospital_name,h.latitude hospital_latitude,h.longitude hospital_longitude FROM emergencies e LEFT JOIN users u ON u.id=e.user_id JOIN emergency_hospitals eh ON eh.emergency_id=e.id AND eh.hospital_id=? JOIN hospitals h ON h.id=eh.hospital_id WHERE eh.status='PENDING' AND e.status='HOSPITAL_BROADCAST' ORDER BY eh.priority_rank ASC,e.id DESC",(hid,)).fetchall()
    out=[]
    for r in rows:
        item=dict(r)
        item['distance_km']=round(dist(r['latitude'],r['longitude'],r['hospital_latitude'],r['hospital_longitude']),2)
        out.append(item)
    c.close(); return jsonify(success=True,emergencies=out)

@app.get('/api/hospital/dispatches')
def h_dispatches():
    hid=session.get('hospital_id')
    if not hid:return jsonify(success=False,message='Hospital login required'),401
    c=db(); rows=c.execute('''SELECT e.id,e.status,e.latitude,e.longitude,e.accepted_at,e.ambulance_id,
        u.name patient_name,u.phone patient_phone,
        d.name driver_name,d.phone driver_phone,d.ambulance_number,
        d.latitude driver_latitude,d.longitude driver_longitude,d.status driver_status
        FROM emergencies e LEFT JOIN users u ON u.id=e.user_id
        LEFT JOIN drivers d ON d.id=e.ambulance_id
        WHERE e.hospital_id=? AND e.status IN ('HOSPITAL_ACCEPTED','DISPATCHED','PICKED_UP')
        ORDER BY e.id DESC''',(hid,)).fetchall(); c.close()
    return jsonify(success=True,dispatches=[dict(r) for r in rows])

@app.post('/api/hospital/respond')
def hrespond():
    d=flask.request.json or {}; eid=d.get('emergency_id'); action=d.get('action'); hid=session.get('hospital_id')
    if not hid:return jsonify(success=False,message='Hospital login required'),401
    if action not in ('ACCEPT','DECLINE'):return jsonify(success=False,message='Invalid action'),400
    c=db(); e=c.execute('SELECT * FROM emergencies WHERE id=?',(eid,)).fetchone(); eh=c.execute('SELECT * FROM emergency_hospitals WHERE emergency_id=? AND hospital_id=?',(eid,hid)).fetchone()
    if not e or not eh:c.close();return jsonify(success=False,message='Request not found'),404
    if action=='DECLINE':
        cur=c.execute("UPDATE emergency_hospitals SET status='DECLINED',responded_at=CURRENT_TIMESTAMP WHERE emergency_id=? AND hospital_id=? AND status='PENDING'",(eid,hid))
        nxt=None
        if cur.rowcount:
            nxt=c.execute("SELECT id,priority_rank FROM emergency_hospitals WHERE emergency_id=? AND status='WAITING' ORDER BY priority_rank LIMIT 1",(eid,)).fetchone()
            if nxt:
                c.execute("UPDATE emergency_hospitals SET status='PENDING',notified_at=CURRENT_TIMESTAMP WHERE id=?",(nxt['id'],))
                log_event(c,eid,'HOSPITAL_ESCALATED',f'Priority hospital declined; emergency sent to hospital rank {nxt["priority_rank"]}.')
            else: log_event(c,eid,'HOSPITAL_DECLINED','Hospital declined the emergency request; no standby hospital remains.')
        c.commit();c.close();return jsonify(success=True,message='Request declined; next-nearest hospital notified.' if nxt else 'Request declined')
    # Atomic first-accept rule: UPDATE succeeds only while broadcast is still active.
    cur=c.execute("UPDATE emergencies SET hospital_id=?,status='HOSPITAL_ACCEPTED',accepted_at=CURRENT_TIMESTAMP WHERE id=? AND status='HOSPITAL_BROADCAST'",(hid,eid))
    if cur.rowcount==0:c.close();return jsonify(success=False,message='Another hospital already accepted this emergency'),409
    log_event(c,eid,'HOSPITAL_ACCEPTED','Hospital accepted the emergency.')
    c.execute("UPDATE emergency_hospitals SET status='ACCEPTED',responded_at=CURRENT_TIMESTAMP WHERE emergency_id=? AND hospital_id=?",(eid,hid))
    c.execute("UPDATE emergency_hospitals SET status='CLOSED' WHERE emergency_id=? AND hospital_id<>? AND status='PENDING'",(eid,hid))
    c.execute('UPDATE hospitals SET occupied=occupied+1 WHERE id=?',(hid,)); c.commit();c.close()
    return jsonify(success=True,message='Hospital accepted. Ambulance dispatch can now begin.')


@app.post('/api/hospital/reached')
def hospital_reached():
    d=flask.request.json or {}
    eid=d.get('emergency_id')
    hid=session.get('hospital_id')
    if not hid:
        return jsonify(success=False,message='Hospital login required'),401
    if not eid:
        return jsonify(success=False,message='Emergency ID required'),400
    c=db()
    e=c.execute('SELECT * FROM emergencies WHERE id=? AND hospital_id=?',(eid,hid)).fetchone()
    if not e:
        c.close(); return jsonify(success=False,message='Emergency not found for this hospital'),404
    if e['status'] not in ('DISPATCHED','PICKED_UP'):
        c.close(); return jsonify(success=False,message='Ambulance has not reached the hospital stage yet'),409
    # Hospital confirms physical arrival. Close the emergency and release the ambulance.
    cur=c.execute("UPDATE emergencies SET status='COMPLETED',completed_at=CURRENT_TIMESTAMP WHERE id=? AND hospital_id=? AND status IN ('DISPATCHED','PICKED_UP')",(eid,hid))
    if cur.rowcount != 1:
        c.close(); return jsonify(success=False,message='Emergency state changed; refresh and retry'),409
    if e['ambulance_id']:
        c.execute("UPDATE drivers SET status='AVAILABLE' WHERE id=?",(e['ambulance_id'],))
    c.execute("UPDATE hospitals SET occupied=CASE WHEN occupied>0 THEN occupied-1 ELSE 0 END WHERE id=?",(hid,))
    log_event(c,eid,'PATIENT_REACHED_HOSPITAL','Hospital confirmed that the patient and ambulance reached the hospital. Patient live GPS tracking stopped and ambulance is available again.')
    c.commit(); c.close()
    return jsonify(success=True,message='Patient reached at hospital. Emergency closed and ambulance is available again.',status='COMPLETED',gps_tracking='STOPPED')

# ---------------- DRIVER ----------------
@app.post('/api/driver/register')
def driver_register():
    d=flask.request.json or {}; required=['name','phone','license_number','ambulance_number','hospital_id','username','password']
    if any(not d.get(k) for k in required):return jsonify(success=False,message='All required driver fields must be filled'),400
    c=db(); h=c.execute('SELECT id FROM hospitals WHERE id=? AND verified=1',(d['hospital_id'],)).fetchone()
    if not h:c.close();return jsonify(success=False,message='Hospital not found or not verified'),400
    try:
        cur=c.execute('''INSERT INTO drivers(name,phone,license_number,ambulance_number,hospital_id,latitude,longitude,status,username,password_hash,verified)
                         VALUES(?,?,?,?,?,?,?,?,?,?,0)''',(d['name'],d['phone'],d['license_number'],d['ambulance_number'],d['hospital_id'],None,None,'OFFLINE',d['username'],generate_password_hash(d['password'])))
        c.commit();return jsonify(success=True,message='Driver registration submitted. Admin verification is required.',driver_id=cur.lastrowid)
    except sqlite3.IntegrityError:return jsonify(success=False,message='Driver username already exists'),409
    finally:c.close()

@app.post('/api/driver/login')
def dlogin():
    d=flask.request.json or {}; c=db(); x=c.execute('SELECT * FROM drivers WHERE username=?',(d.get('username',''),)).fetchone(); c.close()
    if not x or not x['verified'] or not check_password_hash(x['password_hash'],d.get('password','')):return jsonify(success=False,message='Invalid or unverified driver login'),401
    session['driver_id']=x['id'];c=db();c.execute("UPDATE drivers SET status='AVAILABLE' WHERE id=?",(x['id'],));c.commit();c.close();return jsonify(success=True,driver=dict(x))

@app.get('/api/driver/me')
def dme():
    did=session.get('driver_id');c=db();x=c.execute('SELECT * FROM drivers WHERE id=?',(did,)).fetchone() if did else None;c.close();return jsonify(success=bool(x),driver=dict(x) if x else None)

@app.get('/api/driver/emergencies')
def d_emergencies():
    did=session.get('driver_id')
    if not did:return jsonify(success=False,message='Driver login required'),401
    c=db();dr=c.execute('SELECT * FROM drivers WHERE id=?',(did,)).fetchone()
    rows=c.execute('''SELECT e.*,u.name patient_name,u.phone patient_phone,u.age patient_age,u.blood_group patient_blood,
        h.name hospital_name,h.phone hospital_phone,h.latitude hospital_latitude,h.longitude hospital_longitude
        FROM emergencies e LEFT JOIN users u ON u.id=e.user_id JOIN hospitals h ON h.id=e.hospital_id
        WHERE e.status='HOSPITAL_ACCEPTED' AND h.id=? ORDER BY e.id DESC''',(dr['hospital_id'],)).fetchall();c.close();return jsonify(success=True,emergencies=[dict(r) for r in rows])

@app.post('/api/driver/accept')
def daccept():
    d=flask.request.json or {};eid=d.get('emergency_id');did=session.get('driver_id')
    if not did:return jsonify(success=False,message='Driver login required'),401
    c=db();dr=c.execute('SELECT * FROM drivers WHERE id=? AND verified=1',(did,)).fetchone();e=c.execute('SELECT * FROM emergencies WHERE id=?',(eid,)).fetchone()
    if not dr or not e:c.close();return jsonify(success=False,message='Invalid driver/request'),400
    if e['hospital_id'] != dr['hospital_id']:c.close();return jsonify(success=False,message='Driver is not assigned to this hospital'),403
    if dr['status']!='AVAILABLE':c.close();return jsonify(success=False,message='Ambulance unavailable'),409
    cur=c.execute("UPDATE emergencies SET ambulance_id=?,status='DISPATCHED' WHERE id=? AND status='HOSPITAL_ACCEPTED' AND ambulance_id IS NULL",(did,eid))
    if cur.rowcount==0:c.close();return jsonify(success=False,message='Request already assigned'),409
    c.execute("UPDATE drivers SET status='BUSY' WHERE id=?",(did,)); log_event(c,eid,'DISPATCHED',f'{dr["name"]} accepted the dispatch.'); c.commit();c.close();return jsonify(success=True,message='Ambulance dispatched')

@app.post('/api/driver/response-status')
def driver_response_status():
    d=flask.request.json or {}; did=session.get('driver_id'); eid=d.get('emergency_id'); target=d.get('status')
    if not did:return jsonify(success=False,message='Driver login required'),401
    if target not in ('PICKED_UP','COMPLETED'):return jsonify(success=False,message='Invalid response status'),400
    c=db(); e=c.execute('SELECT * FROM emergencies WHERE id=?',(eid,)).fetchone()
    if not e:
        c.close()
        return jsonify(success=False,message='Emergency not found'),404
    if e['ambulance_id'] is not None and e['ambulance_id'] != did:
        c.close()
        return jsonify(success=False,message='Emergency is assigned to another driver'),403
    if target=='PICKED_UP':
        if e['status']!='DISPATCHED':c.close();return jsonify(success=False,message='Patient pickup is not available in the current state'),409
        cur=c.execute("UPDATE emergencies SET status='PICKED_UP' WHERE id=? AND status='DISPATCHED' AND ambulance_id=?",(eid,did))
        if cur.rowcount != 1: c.close(); return jsonify(success=False,message='Emergency state changed; refresh and retry'),409
        log_event(c,eid,'PICKED_UP','Driver marked the patient as picked up.')
    else:
        if e['status']!='PICKED_UP':c.close();return jsonify(success=False,message='Complete is available after pickup'),409
        cur=c.execute("UPDATE emergencies SET status='COMPLETED',completed_at=CURRENT_TIMESTAMP WHERE id=? AND status='PICKED_UP' AND ambulance_id=?",(eid,did))
        if cur.rowcount != 1: c.close(); return jsonify(success=False,message='Emergency state changed; refresh and retry'),409
        c.execute("UPDATE drivers SET status='AVAILABLE' WHERE id=?",(did,));
        if e['hospital_id']: c.execute("UPDATE hospitals SET occupied=CASE WHEN occupied>0 THEN occupied-1 ELSE 0 END WHERE id=?",(e['hospital_id'],))
        log_event(c,eid,'COMPLETED','Emergency response completed; ambulance is available again.')
    c.commit();c.close();return jsonify(success=True,message=target.replace('_',' ').title())

@app.post('/api/driver/location')
def dloc():
    d=flask.request.json or {};did=session.get('driver_id')
    if not did:return jsonify(success=False,message='Driver login required'),401
    try:lat=float(d['latitude']);lon=float(d['longitude'])
    except:return jsonify(success=False,message='Valid GPS required'),400
    c=db();c.execute('UPDATE drivers SET latitude=?,longitude=? WHERE id=?',(lat,lon,did))
    if d.get('emergency_id'):
        c.execute('INSERT INTO locations(emergency_id,driver_id,latitude,longitude) VALUES(?,?,?,?,?)',(d['emergency_id'],did,lat,lon))
    c.commit();c.close();return jsonify(success=True)

@app.post('/api/driver/status')
def dstatus():
    did=session.get('driver_id');d=flask.request.json or {}
    if not did:return jsonify(success=False,message='Driver login required'),401
    status=d.get('status','AVAILABLE');
    if status not in ('AVAILABLE','OFFLINE','BUSY'):return jsonify(success=False,message='Invalid status'),400
    c=db();c.execute('UPDATE drivers SET status=? WHERE id=?',(status,did));c.commit();c.close();return jsonify(success=True)

# ---------------- ADMIN AUTH ----------------
ADMIN_USERNAME = os.environ.get('MEDIRESCUE_ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.environ.get('MEDIRESCUE_ADMIN_PASSWORD', 'admin123')

@app.post('/api/admin/login')
def admin_login():
    d = flask.request.json or {}
    if d.get('username') != ADMIN_USERNAME or d.get('password') != ADMIN_PASSWORD:
        return jsonify(success=False, message='Invalid admin login'), 401
    session['admin_id'] = 'admin'
    return jsonify(success=True, message='Admin login successful')

@app.get('/api/admin/me')
def admin_me():
    return jsonify(success=bool(session.get('admin_id')), logged_in=bool(session.get('admin_id')))

def require_admin():
    return None if session.get('admin_id') else jsonify(success=False, message='Admin login required'), 401

# ---------------- ADMIN ----------------
@app.get('/api/admin/overview') # type: ignore
def overview():
    guard = require_admin()
    if guard: return guard
    c=db();out={'users':c.execute('SELECT COUNT(*) FROM users').fetchone()[0],
      'hospitals':c.execute('SELECT COUNT(*) FROM hospitals WHERE verified=1').fetchone()[0],
      'pending_hospitals':c.execute('SELECT COUNT(*) FROM hospitals WHERE verified=0').fetchone()[0],
      'drivers':c.execute('SELECT COUNT(*) FROM drivers WHERE verified=1').fetchone()[0],
      'pending_drivers':c.execute('SELECT COUNT(*) FROM drivers WHERE verified=0').fetchone()[0],
      'active':c.execute("SELECT COUNT(*) FROM emergencies WHERE status IN ('HOSPITAL_BROADCAST','HOSPITAL_ACCEPTED','DISPATCHED','PICKED_UP')").fetchone()[0]};c.close();return jsonify(out)

@app.get('/api/admin/pending') # type: ignore
def pending():
    guard = require_admin()
    if guard: return guard
    c=db();hs=c.execute('SELECT id,name,phone,address,username,verified FROM hospitals WHERE verified=0 ORDER BY id DESC').fetchall();ds=c.execute('SELECT id,name,phone,license_number,ambulance_number,hospital_id,username,verified FROM drivers WHERE verified=0 ORDER BY id DESC').fetchall();c.close();return jsonify(hospitals=[dict(x) for x in hs],drivers=[dict(x) for x in ds])

@app.post('/api/admin/verify') # type: ignore
def verify():
    guard = require_admin()
    if guard: return guard
    d=flask.request.json or {};kind=d.get('kind');item_id=d.get('id');approved=bool(d.get('approved'))
    if kind not in ('hospital','driver'):return jsonify(success=False,message='Invalid type'),400
    table='hospitals' if kind=='hospital' else 'drivers';c=db();cur=c.execute(f'UPDATE {table} SET verified=? WHERE id=?',(1 if approved else -1,item_id));c.commit();c.close()
    return jsonify(success=cur.rowcount>0,message=('Approved' if approved else 'Rejected'))

@app.post('/api/admin/hospital') # type: ignore
def add_hospital():
    guard = require_admin()
    if guard: return guard
    d=flask.request.json or {};c=db()
    try:
        cur=c.execute('''INSERT INTO hospitals(name,phone,emergency_phone,address,latitude,longitude,capacity,occupied,emergency_available,status,username,password_hash,verified)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1)''',(d['name'],d['phone'],d.get('emergency_phone'),d.get('address'),float(d['latitude']),float(d['longitude']),int(d.get('capacity') or 20),0,1,'ONLINE',d.get('username'),generate_password_hash(d.get('password','hospital123'))));c.commit();return jsonify(success=True,hospital_id=cur.lastrowid)
    except Exception as ex:return jsonify(success=False,message=str(ex)),400
    finally:c.close()

@app.post('/api/admin/driver') # type: ignore
def add_driver():
    guard = require_admin()
    if guard: return guard
    d=flask.request.json or {};c=db()
    try:
        cur=c.execute('''INSERT INTO drivers(name,phone,license_number,ambulance_number,hospital_id,latitude,longitude,status,username,password_hash,verified)
        VALUES(?,?,?,?,?,?,?,?,?,?,1)''',(d['name'],d['phone'],d.get('license_number'),d['ambulance_number'],d['hospital_id'],d.get('latitude'),d.get('longitude'),'AVAILABLE',d.get('username'),generate_password_hash(d.get('password','driver123'))));c.commit();return jsonify(success=True,driver_id=cur.lastrowid)
    except Exception as ex:return jsonify(success=False,message=str(ex)),400
    finally:c.close()

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
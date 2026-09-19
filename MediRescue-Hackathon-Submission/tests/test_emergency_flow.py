import os
import sqlite3
import tempfile
import unittest

import app as application


class MediRescueEmergencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db_path = os.path.join(cls.tmp.name, 'test_medirescue.db')
        application.DB = cls.db_path
        application.app.config.update(TESTING=True, SECRET_KEY='test-secret')
        # Keep tests completely local: no AWS/network side effects.
        application.mirror_emergency = lambda *args, **kwargs: {'mocked': True}
        application.notify = lambda *args, **kwargs: {'mocked': True}
        application.init_db()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.patient = application.app.test_client()
        self.hospital = application.app.test_client()
        self.driver = application.app.test_client()

    def json(self, client, method, path, payload=None):
        return getattr(client, method)(path, json=payload or {})

    def create_pending_sos(self):
        r = self.json(self.patient, 'post', '/api/sos/start', {
            'latitude': 28.98, 'longitude': 77.70, 'accuracy': 8
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json['success'])
        return r.json['emergency_id']

    def hospital_login(self):
        r = self.json(self.hospital, 'post', '/api/hospital/login', {
            'username': 'demo_hospital', 'password': 'hospital123'
        })
        self.assertEqual(r.status_code, 200)

    def driver_login(self):
        r = self.json(self.driver, 'post', '/api/driver/login', {
            'username': 'demo_driver', 'password': 'driver123'
        })
        self.assertEqual(r.status_code, 200)

    def broadcast(self, eid):
        r = self.json(self.patient, 'post', '/api/sos/confirm', {'emergency_id': eid})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json['success'])

    def test_sos_starts_in_safety_window(self):
        eid = self.create_pending_sos()
        r = self.json(self.patient, 'get', f'/api/emergency/{eid}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['emergency']['status'], 'PENDING_CONFIRMATION')

    def test_cancel_prevents_broadcast(self):
        eid = self.create_pending_sos()
        r = self.json(self.patient, 'post', '/api/sos/cancel', {'emergency_id': eid})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json['success'])
        r = self.json(self.patient, 'post', '/api/sos/confirm', {'emergency_id': eid})
        self.assertEqual(r.status_code, 400)

    def test_duplicate_confirm_is_idempotent(self):
        eid = self.create_pending_sos()
        self.broadcast(eid)
        r = self.json(self.patient, 'post', '/api/sos/confirm', {'emergency_id': eid})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json['success'])
        self.assertEqual(r.json['status'], 'HOSPITAL_BROADCAST')

    def test_hospital_can_accept_only_once(self):
        eid = self.create_pending_sos()
        self.broadcast(eid)
        self.hospital_login()
        r = self.json(self.hospital, 'post', '/api/hospital/respond', {
            'emergency_id': eid, 'action': 'ACCEPT'
        })
        self.assertEqual(r.status_code, 200)
        r = self.json(self.hospital, 'post', '/api/hospital/respond', {
            'emergency_id': eid, 'action': 'ACCEPT'
        })
        self.assertEqual(r.status_code, 409)

    def test_driver_full_lifecycle_and_invalid_complete(self):
        eid = self.create_pending_sos()
        self.broadcast(eid)
        self.hospital_login()
        self.assertEqual(self.json(self.hospital, 'post', '/api/hospital/respond', {
            'emergency_id': eid, 'action': 'ACCEPT'
        }).status_code, 200)

        self.driver_login()
        r = self.json(self.driver, 'post', '/api/driver/response-status', {
            'emergency_id': eid, 'status': 'COMPLETED'
        })
        self.assertEqual(r.status_code, 409)

        r = self.json(self.driver, 'post', '/api/driver/accept', {'emergency_id': eid})
        self.assertEqual(r.status_code, 200)
        r = self.json(self.driver, 'post', '/api/driver/response-status', {
            'emergency_id': eid, 'status': 'PICKED_UP'
        })
        self.assertEqual(r.status_code, 200)
        r = self.json(self.driver, 'post', '/api/driver/response-status', {
            'emergency_id': eid, 'status': 'COMPLETED'
        })
        self.assertEqual(r.status_code, 200)

        r = self.json(self.patient, 'get', f'/api/emergency/{eid}')
        self.assertEqual(r.json['emergency']['status'], 'COMPLETED')

        c = application.db()
        driver = c.execute('SELECT status FROM drivers WHERE username=?', ('demo_driver',)).fetchone()
        c.close()
        self.assertEqual(driver['status'], 'AVAILABLE')

    def test_pickup_requires_dispatch(self):
        eid = self.create_pending_sos()
        self.broadcast(eid)
        self.hospital_login()
        self.json(self.hospital, 'post', '/api/hospital/respond', {
            'emergency_id': eid, 'action': 'ACCEPT'
        })
        self.driver_login()
        # Still HOSPITAL_ACCEPTED; pickup before driver acceptance must fail.
        r = self.json(self.driver, 'post', '/api/driver/response-status', {
            'emergency_id': eid, 'status': 'PICKED_UP'
        })
        self.assertEqual(r.status_code, 409)

    def test_timeline_contains_real_events(self):
        eid = self.create_pending_sos()
        self.broadcast(eid)
        self.hospital_login()
        self.json(self.hospital, 'post', '/api/hospital/respond', {
            'emergency_id': eid, 'action': 'ACCEPT'
        })
        self.driver_login()
        self.json(self.driver, 'post', '/api/driver/accept', {'emergency_id': eid})
        self.json(self.driver, 'post', '/api/driver/response-status', {
            'emergency_id': eid, 'status': 'PICKED_UP'
        })
        r = self.json(self.patient, 'get', f'/api/emergency/{eid}/timeline')
        self.assertEqual(r.status_code, 200)
        events = [x['event_type'] for x in r.json['timeline']]
        for expected in ('SOS_CREATED', 'HOSPITAL_BROADCAST', 'HOSPITAL_ACCEPTED', 'DISPATCHED', 'PICKED_UP'):
            self.assertIn(expected, events)

    def test_invalid_gps_is_rejected(self):
        r = self.json(self.patient, 'post', '/api/sos/start', {
            'latitude': 999, 'longitude': 77.7, 'accuracy': 5
        })
        self.assertEqual(r.status_code, 400)


if __name__ == '__main__':
    unittest.main(verbosity=2)

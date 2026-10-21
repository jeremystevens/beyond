"""Phase 38 (sign-in for other devices) checks: python -m unittest discover -s tests -v. Requests are made as if
from this PC (127.0.0.1) or from a phone on the home network (192.168.1.50); nothing listens on the network."""
import json
import tempfile
import unittest
from pathlib import Path

import httpx

from app import auth, config, settings


class SignInTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        from app.server import app
        cls.app = app

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATA_DIR, settings.FILE
        config.DATA_DIR = Path(self.temp.name)
        settings.FILE = config.DATA_DIR / 'settings.json'   # never this PC's real settings
        auth._failures.clear()
        self.pc = self.client('127.0.0.1')
        self.phone = self.client('192.168.1.50')

    async def asyncTearDown(self):
        await self.pc.aclose()
        await self.phone.aclose()
        config.DATA_DIR, settings.FILE = self.saved
        self.temp.cleanup()

    def client(self, address):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=(address, 50000)),
                                 base_url='http://beyond.test', headers={'User-Agent': 'Mozilla/5.0 (Linux; Android 14) Chrome/130.0'})

    async def set_password(self, new='correct horse', current=''):
        return await self.pc.post('/api/auth/password', json={'new': new, 'current': current})

    async def sign_in(self, password='correct horse', remember=True, client=None):
        return await (client or self.phone).post('/api/login', json={'password': password, 'remember': remember})

    async def test_this_pc_never_signs_in(self):
        self.assertEqual((await self.pc.get('/api/health')).status_code, 200)
        self.assertEqual((await self.pc.get('/')).status_code, 200)
        login = await self.pc.get('/login?next=/models')
        self.assertEqual((login.status_code, login.headers['location']), (303, '/models'))

    async def test_without_a_password_other_devices_are_kept_out(self):
        page = await self.phone.get('/models?x=1')
        self.assertEqual((page.status_code, page.headers['location']), (303, '/login?next=%2Fmodels%3Fx%3D1'))
        api = await self.phone.get('/api/health')
        self.assertEqual((api.status_code, api.json()['sign_in']), (401, True))
        self.assertEqual((await self.phone.get('/login')).status_code, 200)
        self.assertEqual((await self.phone.get('/static/style.css')).status_code, 200)
        self.assertEqual((await self.phone.get('/static/index.html')).status_code, 303)   # not on the open list
        self.assertFalse((await self.phone.get('/api/auth/state')).json()['password_set'])
        self.assertEqual((await self.sign_in()).status_code, 409)

    async def test_signing_in_opens_beyond_on_that_device(self):
        self.assertEqual((await self.set_password()).status_code, 200)
        self.assertEqual((await self.sign_in('wrong password')).status_code, 401)
        self.assertEqual((await self.phone.get('/api/health')).status_code, 401)
        good = await self.sign_in()
        self.assertEqual(good.status_code, 200)
        cookie = good.headers['set-cookie'].lower()
        self.assertIn('httponly', cookie)
        self.assertIn('samesite=lax', cookie)
        self.assertIn('max-age=2592000', cookie)
        self.assertEqual((await self.phone.get('/api/health')).status_code, 200)
        self.assertEqual((await self.phone.get('/')).status_code, 200)
        self.assertTrue((await self.phone.get('/api/auth/state')).json()['signed_in'])
        devices = (await self.pc.get('/api/auth')).json()['devices']
        self.assertEqual([(d['device'], d['address']) for d in devices], [('Chrome on Android', '192.168.1.50')])
        await self.phone.post('/api/logout')
        self.assertEqual((await self.phone.get('/api/health')).status_code, 401)

    async def test_a_short_sign_in_ends_with_the_browser(self):
        await self.set_password()
        response = await self.sign_in(remember=False)
        self.assertNotIn('max-age', response.headers['set-cookie'].lower())

    async def test_nothing_secret_is_stored(self):
        await self.set_password()
        await self.sign_in()
        key = self.phone.cookies.get(auth.COOKIE)
        saved = (config.DATA_DIR / 'auth.json').read_text(encoding='utf-8')
        self.assertNotIn('correct horse', saved)
        self.assertNotIn(key, saved)
        self.assertEqual(len(json.loads(saved)['sessions']), 1)

    async def test_only_this_pc_manages_the_password_and_devices(self):
        await self.set_password()
        await self.sign_in()
        self.assertEqual((await self.phone.post('/api/auth/password', json={'new': 'something else',
                                                                             'current': 'correct horse'})).status_code, 403)
        self.assertEqual((await self.phone.post('/api/auth/sign-out-all')).status_code, 403)
        self.assertEqual((await self.phone.get('/api/auth')).json()['devices'], [])
        self.assertEqual((await self.phone.post('/api/settings', json={'changes': {}})).status_code, 403)

    async def test_signing_a_device_out_and_changing_the_password(self):
        await self.set_password()
        await self.sign_in()
        device = (await self.pc.get('/api/auth')).json()['devices'][0]
        await self.pc.post('/api/auth/sign-out-device', json={'id': device['id']})
        self.assertEqual((await self.phone.get('/api/health')).status_code, 401)
        await self.sign_in()
        self.assertEqual((await self.set_password('a new password', 'wrong')).status_code, 403)
        self.assertEqual((await self.set_password('a new password', 'correct horse')).status_code, 200)
        self.assertEqual((await self.phone.get('/api/health')).status_code, 401)       # every device signed out
        self.assertEqual((await self.sign_in('a new password')).status_code, 200)
        self.assertEqual((await self.pc.post('/api/auth/remove', json={'current': 'a new password'})).status_code, 200)
        self.assertEqual((await self.phone.get('/api/health')).status_code, 401)

    async def test_weak_passwords_are_refused(self):
        for bad in ('short', ' padded password ', ''):
            with self.subTest(bad=bad):
                self.assertEqual((await self.set_password(bad)).status_code, 400)

    async def test_guessing_is_slowed_down(self):
        await self.set_password()
        for _ in range(5):
            self.assertEqual((await self.sign_in('wrong guess')).status_code, 401)
        blocked = await self.sign_in()
        self.assertEqual(blocked.status_code, 429)
        self.assertIn('Try again in', blocked.json()['error'])
        other = self.client('192.168.1.51')   # another device isn't held up
        self.assertEqual((await self.sign_in(client=other)).status_code, 200)
        await other.aclose()

    async def test_other_websites_cant_act_for_a_signed_in_device(self):
        await self.set_password()
        await self.sign_in()
        evil = await self.phone.post('/api/logout', headers={'Origin': 'https://evil.example'})
        self.assertEqual(evil.status_code, 403)
        same = await self.phone.post('/api/chat', json={'messages': [{'role': 'user', 'content': 'hi'}]},
                                     headers={'Origin': 'http://beyond.test'})
        self.assertNotEqual(same.status_code, 403)

    async def test_sign_in_can_be_switched_off_on_this_pc(self):
        await self.set_password()
        self.assertEqual((await self.phone.post('/api/auth/required', json={'required': False})).status_code, 401)
        off = await self.pc.post('/api/auth/required', json={'required': False})
        self.assertEqual((off.status_code, off.json()['required']), (200, False))
        self.assertEqual((await self.phone.get('/api/health')).status_code, 200)    # open, as before Phase 38
        self.assertEqual((await self.phone.get('/models')).status_code, 200)
        self.assertEqual((await self.phone.get('/login?next=/models')).headers['location'], '/models')
        self.assertTrue((await self.phone.get('/api/auth/state')).json()['signed_in'])
        self.assertEqual((await self.phone.post('/api/settings', json={'changes': {}})).status_code, 403)
        evil = await self.phone.post('/api/logout', headers={'Origin': 'https://evil.example'})
        self.assertEqual(evil.status_code, 403)                                      # still refused
        await self.pc.post('/api/auth/required', json={'required': True})
        self.assertEqual((await self.phone.get('/api/health')).status_code, 401)

    async def admin_sign_in(self, password='admin password 1', remember=True):
        return await self.phone.post('/api/login', json={'password': password, 'remember': remember, 'admin': True})

    async def test_an_administrator_can_manage_beyond_from_another_device(self):
        await self.set_password()
        self.assertEqual((await self.pc.post('/api/auth/password', json={'new': 'correct horse', 'role': 'admin'})).status_code,
                         400)                                                   # must differ from the sign-in password
        self.assertEqual((await self.pc.post('/api/auth/password', json={'new': 'admin password 1', 'role': 'admin'})).status_code,
                         200)
        await self.sign_in()
        self.assertEqual((await self.phone.post('/api/settings', json={'changes': {}})).status_code, 403)
        self.assertEqual((await self.admin_sign_in('correct horse')).status_code, 401)   # the other password
        login = await self.phone.get('/login?admin=1&next=/settings')
        self.assertEqual(login.status_code, 200)                                 # signed in, but not as administrator
        admin = await self.admin_sign_in()
        self.assertEqual(admin.status_code, 200)
        self.assertIn('max-age=604800', admin.headers['set-cookie'].lower())     # 7 days for administrators
        self.assertEqual((await self.phone.post('/api/settings', json={'changes': {}})).status_code, 200)
        self.assertTrue((await self.phone.get('/api/settings')).json()['can_change'])
        self.assertTrue((await self.phone.get('/api/downloads')).json()['can_download'])
        managed = (await self.phone.get('/api/auth')).json()
        self.assertEqual((managed['manage'], managed['local'], managed['admin_set']), (True, False, True))
        self.assertEqual(sorted(d['role'] for d in managed['devices']), ['admin', 'user'])
        # An administrator can manage sign-in too, with the current password.
        changed = await self.phone.post('/api/auth/password', json={'new': 'new user pass', 'current': 'correct horse'})
        self.assertEqual(changed.status_code, 200)
        self.assertTrue((await self.phone.get('/api/auth/state')).json()['admin'])   # still signed in as administrator
        restart = await self.phone.post('/api/restart')
        self.assertNotIn('127.0.0.1', restart.text)

    async def test_admin_and_sign_in_passwords_sign_out_separately(self):
        await self.set_password()
        await self.pc.post('/api/auth/password', json={'new': 'admin password 1', 'role': 'admin'})
        await self.admin_sign_in()
        await self.pc.post('/api/auth/remove', json={'current': 'correct horse'})
        self.assertTrue((await self.phone.get('/api/auth/state')).json()['admin'])   # the admin sign-in stays
        await self.pc.post('/api/auth/remove', json={'current': 'admin password 1', 'role': 'admin'})
        self.assertEqual((await self.phone.get('/api/health')).status_code, 401)

    async def test_administrator_sign_in_works_with_sign_in_switched_off(self):
        await self.pc.post('/api/auth/password', json={'new': 'admin password 1', 'role': 'admin'})
        await self.pc.post('/api/auth/required', json={'required': False})
        self.assertEqual((await self.phone.get('/api/health')).status_code, 200)
        self.assertEqual((await self.phone.post('/api/settings', json={'changes': {}})).status_code, 403)
        self.assertEqual((await self.phone.get('/login?admin=1')).status_code, 200)
        self.assertEqual((await self.admin_sign_in()).status_code, 200)
        self.assertEqual((await self.phone.post('/api/settings', json={'changes': {}})).status_code, 200)

    async def test_sign_in_page_only_goes_back_into_beyond(self):
        for target, expected in (('/models', '/models'), ('//evil.example', '/'), ('https://evil.example', '/'),
                                 ('/\\evil.example', '/')):
            with self.subTest(target=target):
                response = await self.pc.get('/login', params={'next': target})
                self.assertEqual(response.headers['location'], expected)


if __name__ == '__main__':
    unittest.main()

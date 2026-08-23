import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'dyndns_nfsn.py'


class TestJsonSettingsAndManagementApp(unittest.TestCase):
    def load_module(self):
        spec = importlib.util.spec_from_file_location('dyndns_nfsn_module', MODULE_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_load_and_save_settings(self):
        module = self.load_module()

        self.assertTrue(hasattr(module, 'DEFAULT_SETTINGS'))
        self.assertTrue(hasattr(module, 'load_settings'))
        self.assertTrue(hasattr(module, 'save_settings'))

        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / 'settings.json'
            settings = module.load_settings(str(settings_path))
            self.assertIn('NFSN_DOMAIN', settings)

            settings['NFSN_DOMAIN'] = 'example.com'
            settings['NFSN_SUBDOMAIN'] = 'home'
            settings['NFSN_LOGIN'] = 'user'
            settings['NFSN_API_KEY'] = 'secret'
            module.save_settings(settings, str(settings_path))

            saved = json.loads(settings_path.read_text())
            self.assertEqual(saved['NFSN_DOMAIN'], 'example.com')
            self.assertEqual(saved['NFSN_SUBDOMAIN'], 'home')
            self.assertEqual(saved['NFSN_LOGIN'], 'user')
            self.assertEqual(saved['NFSN_API_KEY'], 'secret')

    def test_management_app_updates_settings(self):
        module = self.load_module()

        self.assertTrue(hasattr(module, 'create_app'))

        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / 'settings.json'
            app = module.create_app(config_path=str(settings_path))
            app.testing = True
            client = app.test_client()

            login_response = client.post(
                '/login',
                data={
                    'username': 'admin',
                    'password': 'admin',
                },
                follow_redirects=True,
            )
            self.assertIn(login_response.status_code, (200, 302))

            response = client.post(
                '/settings',
                data={
                    'NFSN_DOMAIN': 'example.com',
                    'NFSN_SUBDOMAIN': 'home',
                    'NFSN_LOGIN': 'user',
                    'NFSN_API_KEY': 'secret',
                    'CHECK_INTERVAL': '300',
                    'LOG_LEVEL': 'INFO',
                },
                follow_redirects=True,
            )

            self.assertIn(response.status_code, (200, 302))
            saved = json.loads(settings_path.read_text())
            self.assertEqual(saved['NFSN_DOMAIN'], 'example.com')
            self.assertEqual(saved['NFSN_SUBDOMAIN'], 'home')
            self.assertEqual(saved['NFSN_LOGIN'], 'user')
            self.assertEqual(saved['NFSN_API_KEY'], 'secret')

    def test_api_status_returns_json_payload(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / 'settings.json'
            app = module.create_app(config_path=str(settings_path))
            app.testing = True
            client = app.test_client()

            login_response = client.post(
                '/login',
                data={'username': 'admin', 'password': 'admin'},
                follow_redirects=True,
            )
            self.assertIn(login_response.status_code, (200, 302))

            status_response = client.get('/api/status')
            self.assertEqual(status_response.status_code, 200)
            payload = status_response.get_json()
            self.assertIsInstance(payload, dict)
            self.assertEqual(payload['enabled'], False)
            self.assertIsInstance(payload['domains'], list)
            self.assertIn('last_run', payload)
            self.assertIn('last_result', payload)
            self.assertIn('last_message', payload)
            self.assertIn('last_public_ip', payload)
            self.assertIn('host_statuses', payload)

    def test_api_health_endpoint(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / 'settings.json'
            app = module.create_app(config_path=str(settings_path))
            app.testing = True
            client = app.test_client()

            login_response = client.post(
                '/login',
                data={'username': 'admin', 'password': 'admin'},
                follow_redirects=True,
            )
            self.assertIn(login_response.status_code, (200, 302))

            health_response = client.get('/api/health')
            self.assertEqual(health_response.status_code, 200)
            health_payload = health_response.get_json()
            self.assertEqual(health_payload['status'], 'ok')
            self.assertEqual(health_payload['enabled'], False)
            self.assertIn('last_run', health_payload)
            self.assertIn('last_result', health_payload)
            self.assertIn('last_public_ip', health_payload)


if __name__ == '__main__':
    unittest.main()

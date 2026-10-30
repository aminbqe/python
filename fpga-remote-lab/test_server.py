import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import server
from upload_auth import hash_password


class LabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upload_password = 'test-upload-password-only'
        cls.password_hash = hash_password(cls.upload_password)
        cls.upload_headers = {'X-Upload-Password': cls.upload_password}

    def setUp(self):
        env = patch.dict(os.environ, {'UPLOAD_PASSWORD_HASH': self.password_hash})
        env.start()
        self.addCleanup(env.stop)

    def test_page_and_disconnected_upload(self):
        with TestClient(server.app) as client:
            self.assertEqual(client.get('/').status_code, 200)
            self.assertEqual(client.post('/api/upload', headers=self.upload_headers, files={'file': ('test.bit', b'test')}).status_code, 503)

    def test_rasp_prefix(self):
        with TestClient(server.app) as client:
            self.assertEqual(client.get('/rasp').status_code, 200)
            self.assertEqual(client.get('/rasp/static/app.js').status_code, 200)
            self.assertEqual(client.post('/rasp/api/upload', headers=self.upload_headers, files={'file': ('test.bit', b'test')}).status_code, 503)
            with client.websocket_connect('/rasp/ws') as ws:
                self.assertEqual(ws.receive_json()['type'], 'state')
                self.assertEqual(ws.receive_json()['type'], 'job')

    def test_agent_program_telemetry_and_stop(self):
        os.environ['AGENT_TOKEN'] = 'test-token-only'
        with TestClient(server.app) as client:
            with client.websocket_connect('/agent', headers={'Authorization': 'Bearer test-token-only'}) as agent:
                with client.websocket_connect('/ws') as browser:
                    self.assertTrue(browser.receive_json()['connected'])
                    self.assertIsNone(browser.receive_json()['job'])
                    bitfile = {'file': ('demo.bit', bytes.fromhex('00090ff00ff00ff00ff000') + b'payload')}
                    # Even with a live hardware agent and a valid file, missing or
                    # incorrect credentials must never start a programming job.
                    for path in ['/api/upload', '/rasp/api/upload']:
                        for headers in [{}, {'X-Upload-Password': 'incorrect-password'}]:
                            self.assertEqual(client.post(path, headers=headers, files=bitfile).status_code, 401)
                            self.assertIsNone(server.job)
                    response = client.post('/api/upload', headers=self.upload_headers, files=bitfile)
                    self.assertEqual(response.status_code, 200)
                    command = agent.receive_json()
                    identifier = command['job']['id']
                    self.assertEqual(client.get(command['download']).status_code, 403)
                    self.assertEqual(client.get(command['download'], headers={'Authorization': 'Bearer test-token-only'}).status_code, 200)
                    self.assertEqual(browser.receive_json()['job']['status'], 'programming')
                    agent.send_json({'type': 'status', 'job_id': identifier, 'status': 'running'})
                    self.assertEqual(browser.receive_json()['job']['status'], 'running')
                    agent.send_json({'type': 'telemetry', 'leds': [True, False, True, False], 'digits': [63] * 6})
                    self.assertEqual(browser.receive_json()['leds'], [True, False, True, False])
                    browser.send_json({'type': 'input', 'kind': 'button', 'index': 0, 'value': True})
                    self.assertEqual(agent.receive_json()['type'], 'input')
                    self.assertEqual(client.post('/api/upload', headers=self.upload_headers, files={'file': ('test.bit', b'test')}).status_code, 409)
                    browser.send_json({'type': 'stop'})
                    self.assertEqual(agent.receive_json()['type'], 'stop')
                    agent.send_json({'type': 'status', 'job_id': identifier, 'status': 'stopped'})
                    self.assertEqual(browser.receive_json()['job']['status'], 'stopped')
                    self.assertIsNone(browser.receive_json()['job'])
                    self.assertFalse((server.UPLOADS / (identifier + '.bit')).exists())

    def test_upload_disabled_without_password_configuration(self):
        with patch.dict(os.environ, {'UPLOAD_PASSWORD_HASH': ''}), TestClient(server.app) as client:
            for path in ['/api/upload', '/rasp/api/upload']:
                response = client.post(path, headers=self.upload_headers, files={'file': ('test.bit', b'test')})
                self.assertEqual(response.status_code, 503)

    def test_malformed_password_configuration_does_not_allow_upload(self):
        with patch.dict(os.environ, {'UPLOAD_PASSWORD_HASH': 'invalid'}), TestClient(server.app) as client:
            self.assertEqual(client.post('/api/upload', headers=self.upload_headers,
                                        files={'file': ('test.bit', b'test')}).status_code, 401)


if __name__ == '__main__':
    unittest.main()

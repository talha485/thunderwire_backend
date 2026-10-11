from datetime import timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase
from .models import Message, Session
from .utils import crc32_hex


class ApiFlowTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pass12345')
        self.bob = User.objects.create_user('bob', password='pass12345')

    def login(self, username='alice'):
        r = self.client.post('/api/login/', {'username': username, 'password': 'pass12345'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['token']}")
        return r.data['token']

    def test_register(self):
        r = self.client.post('/api/register/', {'username': 'carol', 'password': 'x'}, format='json')
        self.assertEqual(r.status_code, 201)
        r = self.client.post('/api/register/', {'username': 'carol', 'password': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_password_is_hashed_not_plaintext(self):
        self.assertTrue(self.alice.password.startswith('pbkdf2_sha256$'))

    def test_login_issues_24h_uuid_token(self):
        token = self.login()
        session = Session.objects.get(token=token)
        lifetime = session.expires_at - session.created_at
        self.assertAlmostEqual(lifetime.total_seconds(), 24 * 3600, delta=5)

    def test_bad_login(self):
        r = self.client.post('/api/login/', {'username': 'alice', 'password': 'nope'}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_protected_endpoints_require_token(self):
        for url in ['/api/users/list/', '/api/messages/history/']:
            self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.post('/api/messages/send/', {}).status_code, 401)
        self.assertEqual(self.client.post('/api/logout/').status_code, 401)

    def test_garbage_and_expired_tokens_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not-a-uuid')
        self.assertEqual(self.client.get('/api/users/list/').status_code, 401)

        token = self.login()
        Session.objects.filter(token=token).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get('/api/users/list/').status_code, 401)
        self.assertFalse(Session.objects.filter(token=token).exists())

    def test_logout_invalidates_token(self):
        self.login()
        self.assertEqual(self.client.post('/api/logout/').status_code, 204)
        self.assertEqual(self.client.get('/api/users/list/').status_code, 401)

    def test_users_list_excludes_self(self):
        self.login()
        r = self.client.get('/api/users/list/')
        self.assertEqual([u['username'] for u in r.data], ['bob'])

    def test_send_and_history(self):
        self.login()
        r = self.client.post('/api/messages/send/', {'recipient_id': self.bob.id, 'content': 'hello bob'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['checksum'], crc32_hex('hello bob'))
        self.assertEqual(r.data['recipient']['username'], 'bob')
        self.assertEqual(r.data['delivery_status'], Message.DeliveryStatus.ACKED)

        self.login('bob')
        r = self.client.get(f'/api/messages/history/?with={self.alice.id}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data[0]['content'], 'hello bob')

    def test_send_validation(self):
        self.login()
        r = self.client.post('/api/messages/send/', {'recipient_id': 9999, 'content': 'hi'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/messages/send/', {'recipient_id': self.bob.id, 'content': '   '}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_history_is_last_50_oldest_first(self):
        for i in range(60):
            Message.objects.create(sender=self.alice, recipient=self.bob, content=str(i), checksum=crc32_hex(str(i)))
        self.login()
        r = self.client.get('/api/messages/history/')
        self.assertEqual(len(r.data), 50)
        self.assertEqual(r.data[0]['content'], '10')
        self.assertEqual(r.data[-1]['content'], '59')

    def test_history_does_not_leak_other_conversations(self):
        carol = User.objects.create_user('carol', password='pass12345')
        Message.objects.create(sender=self.bob, recipient=carol, content='secret', checksum='0')
        self.login()
        self.assertEqual(self.client.get('/api/messages/history/').data, [])

    def test_status_is_public(self):
        r = self.client.get('/api/status/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['database'], 'up')

    def test_cors_allows_vite_dev_server(self):
        r = self.client.get('/api/status/', HTTP_ORIGIN='http://localhost:5173')
        self.assertEqual(r['Access-Control-Allow-Origin'], 'http://localhost:5173')

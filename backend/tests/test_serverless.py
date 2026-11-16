"""Offline smoke tests; no external services or model calls."""
import asyncio
import os
import unittest

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-only-stable-key-not-for-production"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from db.database import Base, get_db
from utils import event_stream


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)

        def database():
            with self.sessions() as session:
                yield session

        app.dependency_overrides[get_db] = database
        # Intentionally no lifespan context: serverless may skip ASGI lifespan.
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_health_and_auth(self):
        self.assertEqual(self.client.get('/api/health').json(), {"status": "ok"})
        response = self.client.post('/api/auth/create', json={
            'username': 'test-user', 'email': 'test@example.com'
        })
        self.assertEqual(response.status_code, 200, response.text)
        headers = {'Authorization': 'Bearer ' + response.json()['token']}
        self.assertEqual(self.client.get('/api/auth/me', headers=headers).json()['username'], 'test-user')
        self.assertEqual(self.client.get('/api/states', headers=headers).json(), [])
        self.assertEqual(self.client.get('/api/states/latest').json(), [])
        self.assertEqual(self.client.get('/api/states/999').status_code, 404)
        self.assertEqual(self.client.get('/api/auth/me', headers={
            'Authorization': 'Bearer invalid'
        }).status_code, 401)


class StreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_completion_closes_generator(self):
        closed = []

        async def stream():
            try:
                yield 'first\n'
                yield 'second\n'
            finally:
                closed.append(True)

        self.assertEqual([item async for item in event_stream.with_heartbeat(stream())],
                         ['first\n', 'second\n'])
        self.assertEqual(closed, [True])

    async def test_timeout_cancels_and_closes_work(self):
        closed = []

        async def stream():
            try:
                await asyncio.sleep(60)
                yield 'unreachable'
            finally:
                closed.append(True)

        old = event_stream.STREAM_TIMEOUT_SECONDS
        event_stream.STREAM_TIMEOUT_SECONDS = 0.01
        try:
            items = [item async for item in event_stream.with_heartbeat(stream())]
        finally:
            event_stream.STREAM_TIMEOUT_SECONDS = old
        self.assertIn('timed out', items[-1])
        self.assertEqual(closed, [True])


if __name__ == '__main__':
    unittest.main()

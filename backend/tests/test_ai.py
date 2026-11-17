import asyncio
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['JWT_SECRET_KEY'] = 'test-only-stable-key-not-for-production'

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from db.database import Base, get_db
from db.models import User, AIResult, AIBudget, State, StateSnapshot
from model.ai_session import AISession, current_ai, AIError
from model.providers import OpenAIProvider
from routers.ai import acquire, release
from utils.event_stream import with_heartbeat
from utils.parallel import gather_cancel_on_error


class AITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', poolclass=StaticPool,
                                    connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            db.add_all([User(id=1, username='alice', email='alice@example.com', credits=0),
                        User(id=2, username='bob', email='bob@example.com', credits=0)])
            db.commit()
        def database():
            with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db] = database
        self.patches = [patch('routers.ai.SessionLocal', self.sessions),
                        patch('model.providers.SessionLocal', self.sessions)]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        from jose import jwt
        from config import JWT_SECRET_KEY
        self.headers = {'Authorization': 'Bearer ' + jwt.encode({'sub': 'alice'}, JWT_SECRET_KEY)}
        self.bob_headers = {'Authorization': 'Bearer ' + jwt.encode({'sub': 'bob'}, JWT_SECRET_KEY)}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        for item in self.patches:
            item.stop()
        self.engine.dispose()

    def test_incomplete_model_output_is_rejected_before_save(self):
        from model.parsing import validate_generated_state
        from model.state_config import DIMENSIONS
        with self.assertRaises(AIError):
            validate_generated_state('not a game state')
        markdown = '\n'.join(f'# {d.title}\n## Overview\nText\n' for d in DIMENSIONS)
        markdown += '\n# Government\n## Government Metadata\n- Country Official Name: Test Nation\n'
        parsed = validate_generated_state(markdown)
        self.assertEqual(parsed['government']['government_metadata']['country_official_name']['value'], 'Test Nation')

    def test_expired_action_lease_recovery_and_old_owner_cannot_release(self):
        with self.sessions() as db, patch('routers.ai.time.time', return_value=1000):
            old_owner = acquire(db, 1)
        with self.sessions() as db, patch('routers.ai.time.time', return_value=1400):
            owner = acquire(db, 1)
            self.assertNotEqual(old_owner, owner)
            release(db, 1, old_owner)
            self.assertEqual(db.get(AIBudget, 1).owner, owner)

    def test_status_is_authenticated_account_scoped_and_does_not_spend_quota(self):
        self.assertIn(self.client.get('/api/ai/status').status_code, (401, 403))
        with patch('routers.ai.time.time', return_value=1000):
            response = self.client.get('/api/ai/status', headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertEqual(response.json()['remaining_actions'], 12)
            with self.sessions() as db:
                self.assertEqual(db.query(AIBudget).count(), 0)
                acquire(db, 1)
            alice = self.client.get('/api/ai/status', headers=self.headers).json()
            bob = self.client.get('/api/ai/status', headers=self.bob_headers).json()
            self.assertEqual(alice['remaining_actions'], 11)
            self.assertTrue(alice['active'])
            self.assertGreater(alice['retry_after_seconds'], 0)
            self.assertEqual(bob['remaining_actions'], 12)
            self.assertFalse(bob['active'])
            again = self.client.get('/api/ai/status', headers=self.headers).json()
            self.assertEqual(again, alice)
        with patch('routers.ai.time.time', return_value=1700):
            status = self.client.get('/api/ai/status', headers=self.headers).json()
            self.assertEqual(status['remaining_actions'], 12)
            self.assertEqual(status['retry_after_seconds'], 0)

    def test_missing_personal_credentials_never_uses_owner_key(self):
        data = {'name': 'Test', 'questions': [{'question': 'Test?', 'value': 1}]}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'owner-must-not-be-used'}):
            response = self.client.post('/api/states', json=data, headers=self.headers)
            self.assertEqual(response.status_code, 400)
            response = self.client.post('/api/states', json=data,
                                       headers={**self.headers, 'X-AI-Provider': 'openai'})
            self.assertEqual(response.status_code, 400)
        with self.sessions() as db:
            self.assertEqual(db.query(AIBudget).count(), 0)

    def test_stream_dependency_context_and_zero_credit_gameplay(self):
        data = {'name': 'Test', 'questions': [{'question': 'Test?', 'value': 1}]}
        seen = []
        async def fail_safely(**kwargs):
            session = current_ai.get()
            seen.append((session.provider, session.key))
            raise AIError('Personal provider quota reached.')
        with patch('routers.states.generate_state', side_effect=fail_safely):
            response = self.client.post('/api/states', json=data, headers={
                **self.headers, 'X-AI-Provider': 'openai', 'X-AI-Key': 'player-secret'
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Personal provider quota', response.text)
        self.assertNotIn('player-secret', response.text)
        self.assertEqual(seen, [('openai', 'player-secret')])
        self.assertIsNone(current_ai.get(None))
        with self.sessions() as db:
            self.assertEqual(db.get(AIBudget, 1).active_until, 0)
            self.assertEqual(db.get(User, 1).credits, 0)

    def test_distributed_budget_cooldown_window_and_owner_release(self):
        with self.sessions() as db, patch('routers.ai.time.time', return_value=1000):
            owner = acquire(db, 1)
            with self.assertRaises(HTTPException) as error:
                acquire(db, 1)
            self.assertEqual(error.exception.status_code, 429)
            release(db, 1, 'wrong-owner')
            self.assertEqual(db.get(AIBudget, 1).owner, owner)
            release(db, 1, owner)
            with self.assertRaises(HTTPException):
                acquire(db, 1)  # cooldown survives normal completion
        with self.sessions() as db, patch('routers.ai.time.time', return_value=1010):
            owner = acquire(db, 1)
            release(db, 1, owner)
            budget = db.get(AIBudget, 1)
            budget.count = 12
            db.commit()
        with self.sessions() as db, patch('routers.ai.time.time', return_value=1020):
            with self.assertRaises(HTTPException):
                acquire(db, 1)
        with self.sessions() as db, patch('routers.ai.time.time', return_value=1700):
            acquire(db, 1)
            self.assertEqual(db.get(AIBudget, 1).count, 1)

    def test_result_ownership_expiry_duplicate_and_size(self):
        with self.sessions() as db:
            db.add(AIResult(id='job', user_id=1, expires_at=datetime.now(timezone.utc) + timedelta(minutes=1)))
            db.add(AIResult(id='old', user_id=1, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
            db.commit()
        path = '/api/ai/results/job'
        self.assertEqual(self.client.post(path, json={'content': 'forged'}, headers=self.bob_headers).status_code, 404)
        self.assertEqual(self.client.post('/api/ai/results/old', json={'content': 'late'}, headers=self.headers).status_code, 404)
        self.assertEqual(self.client.post(path, json={'content': 'x' * 500001}, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.post(path, json={'content': 'ok'}, headers=self.headers).status_code, 204)
        self.assertEqual(self.client.post(path, json={'content': 'duplicate'}, headers=self.headers).status_code, 404)

    async def test_browser_relay_and_cleanup(self):
        session = AISession(1, 'puter', 'test-model')
        token = current_ai.set(session)
        async def stream():
            yield await OpenAIProvider().generate_low_reasoning('test prompt')
        output = []
        try:
            async for item in with_heartbeat(stream()):
                if item.startswith('{'):
                    event = json.loads(item)
                    if event['type'] == 'ai_request':
                        self.assertEqual(event['prompt'], 'test prompt')
                        response = self.client.post('/api/ai/results/' + event['request_id'],
                                                    json={'content': 'model result'}, headers=self.headers)
                        self.assertEqual(response.status_code, 204)
                else:
                    output.append(item)
        finally:
            current_ai.reset(token)
        self.assertEqual(output, ['model result'])
        with self.sessions() as db:
            self.assertEqual(db.query(AIResult).count(), 0)

    async def test_browser_cancellation_cleans_mailbox(self):
        token = current_ai.set(AISession(1, 'puter', 'test-model'))
        task = asyncio.create_task(OpenAIProvider().generate_low_reasoning('prompt'))
        try:
            await current_ai.get().events.get()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        finally:
            current_ai.reset(token)
        with self.sessions() as db:
            self.assertEqual(db.query(AIResult).count(), 0)

    async def test_parallel_failure_cancels_sibling(self):
        closed = []
        async def fails():
            await asyncio.sleep(0)
            raise AIError('safe')
        async def waits():
            try:
                await asyncio.sleep(60)
            finally:
                closed.append(True)
        with self.assertRaises(AIError):
            await gather_cancel_on_error(fails(), waits())
        self.assertEqual(closed, [True])

    async def test_key_isolation_across_concurrent_requests(self):
        calls = []
        class FakeClient:
            def __init__(self, **kwargs):
                self.key = kwargs['api_key']
                self.chat = self.completions = self
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def create(self, **kwargs):
                await asyncio.sleep(0)
                calls.append((self.key, kwargs['model']))
                from types import SimpleNamespace as NS
                return NS(choices=[NS(message=NS(content='ok'))])
        async def run(key):
            token = current_ai.set(AISession(1, 'openai', key + '-model', key))
            try:
                return await OpenAIProvider().generate_high_reasoning('prompt')
            finally:
                current_ai.reset(token)
        with patch('model.providers.AsyncOpenAI', FakeClient):
            self.assertEqual(await asyncio.gather(run('alice'), run('bob')), ['ok', 'ok'])
        self.assertCountEqual(calls, [('alice', 'alice-model'), ('bob', 'bob-model')])


    def test_private_state_and_snapshot_reads_are_owner_scoped(self):
        from model.state_config import DIMENSIONS

        with self.sessions() as db:
            alice_state = State(
                name='Alice nation', date='2022-01', description='private',
                flag_svg='<svg></svg>', user_id=1,
                updated_at=datetime.now(timezone.utc),
            )
            bob_state = State(
                name='Bob nation', date='2022-01', description='private',
                flag_svg='<svg></svg>', user_id=2,
                updated_at=datetime.now(timezone.utc),
            )
            db.add_all([alice_state, bob_state])
            db.commit()
            db.refresh(alice_state)
            db.refresh(bob_state)

            markdown = '\n'.join(
                f'# {dimension.title}\n## Overview\nText\n'
                for dimension in DIMENSIONS
            )
            markdown += '\n# Government\n## Government Metadata\n- Country Official Name: Alice Republic\n'
            db.add(StateSnapshot(
                date='2022-01', state_id=alice_state.id,
                markdown_state=markdown,
                markdown_future_events='No notable events',
                markdown_future_events_policy='',
            ))
            db.commit()
            alice_id, bob_id = alice_state.id, bob_state.id

        self.assertEqual(
            self.client.get(f'/api/states/{alice_id}', headers=self.headers).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f'/api/states/{bob_id}', headers=self.headers).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f'/api/states/{alice_id}/snapshots', headers=self.headers).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f'/api/states/{bob_id}/snapshots', headers=self.headers).status_code,
            404,
        )
        self.assertIn(
            self.client.get(f'/api/states/{alice_id}').status_code,
            (401, 403),
        )
        self.assertIn(
            self.client.get(f'/api/states/{alice_id}/snapshots').status_code,
            (401, 403),
        )

    def test_setup_answers_are_limited_to_the_five_point_scale(self):
        from pydantic import ValidationError
        from routers.schemas import QuestionInput

        self.assertEqual(QuestionInput(question='Test?', value=3).value, 3)
        for invalid_value in (0, 6, -1, 10):
            with self.subTest(value=invalid_value):
                with self.assertRaises(ValidationError):
                    QuestionInput(question='Test?', value=invalid_value)

    def test_empty_event_distribution_has_a_safe_fallback(self):
        from model.actions import _sample_event

        self.assertEqual(_sample_event([]), 'No notable events')
        self.assertEqual(_sample_event([(0.0, '  ')]), 'No notable events')

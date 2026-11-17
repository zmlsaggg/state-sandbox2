import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const aiSource = await readFile(new URL('../src/lib/ai.js', import.meta.url), 'utf8');
const aiURL = 'data:text/javascript;base64,' + Buffer.from(aiSource).toString('base64');
const ai = await import(aiURL);
const apiSource = (await readFile(new URL('../src/lib/api.js', import.meta.url), 'utf8')).replace("'./ai'", JSON.stringify(aiURL));
const { api } = await import('data:text/javascript;base64,' + Buffer.from(apiSource).toString('base64'));

beforeEach(() => {
  ai.clearAISettings();
  ai.setAISettings({ provider: 'puter', model: 'gpt-4o-mini', key: '' });
  globalThis.localStorage = { getItem: () => 'game-token' };
  globalThis.window = { location: { origin: 'https://game.example' }, puter: {
    auth: { isSignedIn: () => true },
    ai: { chat: async () => ({ message: { content: 'browser model response' } }) },
  } };
});

test('BYOK is explicit, memory-only, clearable, and absent from Puter headers', async () => {
  ai.setAISettings({ provider: 'openai', model: 'model', key: 'personal-secret' });
  assert.equal((await ai.aiHeaders())['X-AI-Key'], 'personal-secret');
  ai.clearAISettings();
  assert.equal(ai.getAISettings().key, '');
  await assert.rejects(ai.aiHeaders(), /Connect Puter/);
  ai.setAISettings({ provider: 'puter', model: 'gpt-4o-mini', key: '' });
  assert.equal((await ai.aiHeaders())['X-AI-Key'], undefined);
  ai.setAISettings({ provider: 'openai', model: 'model', key: '' });
  await assert.rejects(ai.aiHeaders(), /personal AI key/);
});

test('Puter must be connected explicitly before starting gameplay', async () => {
  window.puter.auth.isSignedIn = () => false;
  await assert.rejects(ai.aiHeaders(), /Connect Puter/);
});

test('stream relays Puter result without sending a Puter token or personal key', async () => {
  let controller;
  const calls = [];
  const encoder = new TextEncoder();
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    if (url.includes('/api/ai/results/')) {
      assert.deepEqual(JSON.parse(options.body), { content: 'browser model response', error: false });
      controller.enqueue(encoder.encode('{"type":"complete"}\n'));
      controller.close();
      return new Response(null, { status: 204 });
    }
    return new Response(new ReadableStream({ start(c) {
      controller = c;
      c.enqueue(encoder.encode('{"type":"ai_request","request_id":"request-id","prompt":"hello","model":"gpt-4o-mini"}\n'));
    } }));
  };
  const events = [];
  await api._postStream('/api/states', {}, event => events.push(event));
  assert.deepEqual(events, [{ type: 'complete' }]);
  assert.equal(calls.length, 2);
  assert.equal(calls[0].options.headers['X-AI-Key'], undefined);
  assert.equal(calls[1].options.headers.Authorization, 'Bearer game-token');
});

test('Puter rejection delivers only a sanitized failure', async () => {
  window.puter.ai.chat = async () => { throw new Error('secret vendor detail'); };
  let controller;
  globalThis.fetch = async (url, options) => {
    if (url.includes('/api/ai/results/')) {
      assert.deepEqual(JSON.parse(options.body), { content: '', error: true });
      controller.enqueue(new TextEncoder().encode('{"type":"error","message":"Puter failed"}\n'));
      controller.close();
      return new Response(null, { status: 204 });
    }
    return new Response(new ReadableStream({ start(c) {
      controller = c;
      c.enqueue(new TextEncoder().encode('{"type":"ai_request","request_id":"id","prompt":"test","model":"model"}\n'));
    } }));
  };
  await api._postStream('/api/states', {}, () => {});
});

test('abruptly ended streams produce a visible failure', async () => {
  globalThis.fetch = async () => new Response('{"type":"status","message":"started"}\n');
  await assert.rejects(api._postStream('/api/states', {}, () => {}), /interrupted/);
});

test('rate limit message includes retry interval', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Please wait.' }),
    { status: 429, headers: { 'Retry-After': '8' } });
  await assert.rejects(api._postStream('/api/states', {}, () => {}), /Retry in 8 seconds/);
});

test('Puter SDK load failure can be retried instead of leaving a rejected cache', async () => {
  delete window.puter;
  let attempts = 0;
  globalThis.document = {
    createElement: () => ({ remove() {} }),
    head: { appendChild(script) {
      attempts++;
      queueMicrotask(() => {
        if (attempts === 1) { script.onerror(); return; }
        window.puter = { auth: { isSignedIn: () => false } };
        script.onload();
      });
    } },
  };
  await assert.rejects(ai.loadPuter(), /Could not load Puter/);
  assert.equal(await ai.loadPuter(), window.puter);
  assert.equal(attempts, 2);
});

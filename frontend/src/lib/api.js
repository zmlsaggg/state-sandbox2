import { aiHeaders, runPuterRequest } from './ai';
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || '';

const TOKEN_KEY = 'state-sandbox-token';

class ApiClient {
  async _post(endpoint, data) {
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}`,
      },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(res.status === 429
        ? `${errorData.detail} Retry in ${res.headers.get('Retry-After') || 'a few'} seconds.`
        : errorData.detail || `API error: ${res.statusText}`);
    }

    return res.json();
  }

  async _postStream(endpoint, data, onMessage) {
    const personalAI = await aiHeaders();
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...personalAI,
        Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}`,
      },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(res.status === 429
        ? `${errorData.detail} Retry in ${res.headers.get('Retry-After') || 'a few'} seconds.`
        : errorData.detail || `API error: ${res.statusText}`);
    }

    const callbackAbort = new AbortController();
    let active = true;
    let relayError = null;
    let terminal = false;
    const dispatch = event => {
      if (event.type !== 'ai_request') {
        if (['complete', 'state_snapshot_complete', 'advice', 'error'].includes(event.type)) terminal = true;
        onMessage(event); return;
      }
      if (personalAI['X-AI-Provider'] !== 'puter') throw new Error('Unexpected browser AI request.');
      void (async () => {
        let result;
        try { result = { content: await runPuterRequest(event), error: false }; }
        catch { result = { content: '', error: true }; }
        if (!active) return;
        const delivered = await fetch(`${API_URL}/api/ai/results/${encodeURIComponent(event.request_id)}`, {
          method: 'POST', signal: callbackAbort.signal,
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}` },
          body: JSON.stringify(result),
        });
        if (!delivered.ok) throw new Error('Could not deliver Puter result. Please retry.');
      })().catch(error => { if (active) relayError = error; });
    };
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        if (relayError) throw relayError;
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.trim()) {
            const event = JSON.parse(line);
            dispatch(event);
          }
        }
      }

      buffer += decoder.decode();
      if (buffer.trim()) {
        const event = JSON.parse(buffer);
        dispatch(event);
      }
      if (relayError) throw relayError;
      if (!terminal) throw new Error('AI connection was interrupted. Please retry.');
    } finally {
      active = false;
      callbackAbort.abort();
      await reader.cancel().catch(() => {});
      reader.releaseLock();
    }
  }

  async _get(endpoint, params) {
    const url = new URL(`${API_URL}${endpoint}`, window.location.origin);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, value);
        }
      });
    }

    const res = await fetch(url, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}`,
      },
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(res.status === 429
        ? `${errorData.detail} Retry in ${res.headers.get('Retry-After') || 'a few'} seconds.`
        : errorData.detail || `API error: ${res.statusText}`);
    }

    return res.json();
  }

  async _delete(endpoint) {
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}`,
      },
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(res.status === 429
        ? `${errorData.detail} Retry in ${res.headers.get('Retry-After') || 'a few'} seconds.`
        : errorData.detail || `API error: ${res.statusText}`);
    }

    return res.json();
  }

  async _patch(endpoint, data) {
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}`,
      },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(res.status === 429
        ? `${errorData.detail} Retry in ${res.headers.get('Retry-After') || 'a few'} seconds.`
        : errorData.detail || `API error: ${res.statusText}`);
    }

    return res.json();
  }

  async _put(endpoint, data) {
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}`,
      },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(res.status === 429
        ? `${errorData.detail} Retry in ${res.headers.get('Retry-After') || 'a few'} seconds.`
        : errorData.detail || `API error: ${res.statusText}`);
    }

    return res.json();
  }

  async getLatestSnapshots(valueKeys) {
    return this._get('/api/states/latest', { valueKeys: valueKeys.join(',') });
  }

  async createAccount(username, email) {
    const data = await this._post('/api/auth/create', { username, email });
    localStorage.setItem(TOKEN_KEY, data.token);
    return data.user;
  }

  async getAIStatus() {
    return this._get('/api/ai/status');
  }

  async getCurrentUser() {
    return this._get('/api/auth/me');
  }

  async getStates() {
    return this._get('/api/states');
  }

  async getStateSnapshots(stateId) {
    return this._get(`/api/states/${stateId}/snapshots`);
  }

  async createState(name, questions, onMessage) {
    return this._postStream('/api/states', { name, questions }, onMessage);
  }

  async getState(stateId) {
    return this._get(`/api/states/${stateId}`);
  }

  async createStateSnapshot(stateId, policy, onMessage) {
    return this._postStream(
      `/api/states/${stateId}/snapshots`,
      { policy },
      onMessage
    );
  }

  async getStateAdvice(stateId, question, events) {
    let advice;
    await this._postStream(`/api/states/${stateId}/advice`, {
      question, events: events?.join('\n') || '',
    }, event => {
      if (event.type === 'error') throw new Error(event.message);
      if (event.type === 'advice') advice = event;
    });
    if (!advice) throw new Error('Advice was not completed. Please retry.');
    return advice;
  }

  async emailLogin(token) {
    const res = await this._get(`/api/auth/email-login/${token}`);
    localStorage.setItem(TOKEN_KEY, res.token);
    return res.user;
  }

  async updateEmail(email) {
    return this._put('/api/auth/update-email', { email });
  }
}

// Export singleton instance
export const api = new ApiClient();

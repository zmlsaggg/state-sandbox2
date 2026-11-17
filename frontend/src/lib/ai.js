// Personal keys live in this tab's JS memory only, never local/session storage.
let settings = { provider: 'puter', model: 'gpt-4o-mini', key: '', connected: false };
let sdkPromise;

export function getAISettings() { return { ...settings }; }
export function setAISettings(value) { settings = { ...value, connected: true }; }
export function clearAISettings() {
  settings = { provider: 'puter', model: 'gpt-4o-mini', key: '', connected: false };
}

export function loadPuter() {
  if (window.puter) return Promise.resolve(window.puter);
  if (!sdkPromise) {
    sdkPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://js.puter.com/v2/';
      script.async = true;
      const timeout = setTimeout(() => fail('Puter loading timed out. Please retry.'), 15000);
      const fail = message => {
        clearTimeout(timeout);
        script.onload = script.onerror = null;
        script.remove();
        reject(new Error(message));
      };
      script.onload = () => {
        if (!window.puter) { fail('Puter SDK unavailable. Please retry.'); return; }
        clearTimeout(timeout);
        script.onload = script.onerror = null;
        resolve(window.puter);
      };
      script.onerror = () => fail('Could not load Puter. Check your connection.');
      document.head.appendChild(script);
    }).catch(error => {
      sdkPromise = null;
      throw error;
    });
  }
  return sdkPromise;
}

export async function aiHeaders() {
  const { provider, model, key, connected } = settings;
  if (!model.trim()) throw new Error('Select an AI model in Account settings.');
  if (provider === 'puter') {
    const puter = window.puter;
    if (!connected || !puter || !puter.auth.isSignedIn()) throw new Error('Connect Puter in Account settings first.');
  } else if (!key.trim()) {
    throw new Error('Enter your personal AI key in Account settings. It must be re-entered after reloading.');
  }
  return {
    'X-AI-Provider': provider, 'X-AI-Model': model,
    ...(provider !== 'puter' ? { 'X-AI-Key': key } : {}),
  };
}

export async function runPuterRequest(event) {
  const puter = await loadPuter();
  const result = await puter.ai.chat(event.prompt, { model: event.model, stream: false });
  const content = result?.message?.content;
  const text = typeof content === 'string' ? content : Array.isArray(content)
    ? content.filter(part => part.type === 'text').map(part => part.text).join('\n') : '';
  if (!text.trim() || text.length > 500000) throw new Error('Puter returned empty or oversized output.');
  return text;
}

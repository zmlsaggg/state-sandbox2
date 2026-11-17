'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { api } from '@/lib/api';
import { getAISettings, setAISettings, clearAISettings, loadPuter } from '@/lib/ai';

const models = { puter: 'gpt-4o-mini', openai: 'gpt-4o-mini', groq: 'llama-3.3-70b-versatile', openrouter: 'openai/gpt-4o-mini' };

export function AISettings() {
  const [value, setValue] = useState({ provider: 'puter', model: models.puter, key: '' });
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [budget, setBudget] = useState(null);
  const [budgetError, setBudgetError] = useState('');
  const [budgetLoading, setBudgetLoading] = useState(false);
  useEffect(() => {
    let alive = true;
    api.getAIStatus().then(value => { if (alive) setBudget(value); })
      .catch(() => { if (alive) setBudgetError('Could not load current limits. Refresh to retry.'); });
    return () => { alive = false; };
  }, []);
  async function refreshBudget() {
    setBudgetLoading(true); setBudgetError('');
    try { setBudget(await api.getAIStatus()); }
    catch { setBudgetError('Could not load current limits. Refresh to retry.'); }
    finally { setBudgetLoading(false); }
  }
  useEffect(() => { setValue(getAISettings()); }, []);
  async function enablePuter() {
    setBusy(true); setMessage('');
    try { await loadPuter(); setReady(true); }
    catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }

  async function connect() {
    setBusy(true); setMessage('');
    try {
      if (value.provider === 'puter') {
        // SDK preloaded above so signIn starts from the explicit user click.
        if (!window.puter.auth.isSignedIn()) await window.puter.auth.signIn();
        if (!window.puter.auth.isSignedIn()) throw new Error('Puter sign-in was not completed.');
      } else if (!value.key.trim()) throw new Error('Enter your own API key.');
      if (!value.model.trim()) throw new Error('Enter a model name.');
      setAISettings({ ...value, key: value.key.trim(), model: value.model.trim() });
      setMessage('AI connected for this tab. Provider access is checked on the next game action.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Puter connection failed. Please retry.');
    } finally { setBusy(false); }
  }

  return <Card>
    <CardHeader><CardTitle>Your AI provider</CardTitle></CardHeader>
    <CardContent className="space-y-4">
      <p className="text-sm text-muted-foreground">Use your Puter account or your own API key. No owner-funded fallback and no game credits are charged for AI actions. Your provider may impose quotas or charge you; free unlimited usage is not guaranteed.</p>
      <label className="block text-sm">Provider
        <select className="mt-1 w-full rounded border bg-background p-2" value={value.provider}
          onChange={e => { setValue({ provider: e.target.value, model: models[e.target.value], key: '' }); setMessage(''); }}>
          <option value="puter">Puter (browser account)</option><option value="openai">OpenAI (your key)</option>
          <option value="groq">Groq (your key)</option><option value="openrouter">OpenRouter (your key)</option>
        </select>
      </label>
      <label className="block text-sm">Model
        <Input maxLength={160} value={value.model} onChange={e => setValue({ ...value, model: e.target.value })} />
      </label>
      <p className="text-xs text-muted-foreground">Use a model available to your account with strong Markdown, structured-output and long-context support. Smaller models may fail to produce valid game states.</p>
      {value.provider !== 'puter' && <label className="block text-sm">Personal API key
        <Input type="password" autoComplete="off" spellCheck={false} maxLength={4096} value={value.key} onChange={e => setValue({ ...value, key: e.target.value })} />
      </label>}
      <p className="text-xs text-muted-foreground">Personal keys are sent over HTTPS to this game server only for the current action and are not saved by the app. They are held in tab memory and disappear on reload. Puter runs in your browser; its SDK manages its own login. Connecting Puter loads third-party code into this page. Only connect services you trust.</p>
      <div className="flex gap-2">
        {value.provider === 'puter' && !ready && <Button disabled={busy} onClick={enablePuter}>Enable Puter SDK</Button>}
        <Button disabled={busy || (value.provider === 'puter' && !ready)} onClick={connect}>{busy ? 'Connecting…' : value.provider === 'puter' ? 'Connect Puter' : 'Use my key'}</Button>
        <Button variant="outline" onClick={() => { clearAISettings(); setValue(getAISettings()); setMessage('Game AI settings cleared. Puter sign-out is managed separately in your Puter account.'); }}>Clear settings</Button>
      </div>
      <p role="status" className="text-sm">{message}</p>
      <div className="space-y-2 border-t pt-4 text-sm" aria-live="polite">
        {budget && <>
          <p>Allowance: {budget.limits.actions} actions per {budget.limits.window_seconds} seconds; {budget.limits.cooldown_seconds}-second minimum pause between starts.</p>
          <p>Remaining in this window: <strong>{budget.remaining_actions}</strong>. {budget.active ? 'An AI action is currently active.' : 'No AI action is active.'}</p>
          {budget.retry_after_seconds > 0 && <p>Retry in up to {budget.retry_after_seconds} seconds (as of last refresh; active actions may finish sooner).</p>}
        </>}
        <p className="text-muted-foreground">One active action per account. A whole turn counts as one action, not one per internal AI call. Keep this tab open during generation.</p>
        {budgetError && <p role="alert">{budgetError}</p>}
        <Button variant="outline" size="sm" disabled={budgetLoading} onClick={refreshBudget}>{budgetLoading ? 'Refreshing…' : 'Refresh current limits'}</Button>
      </div>
    </CardContent>
  </Card>;
}

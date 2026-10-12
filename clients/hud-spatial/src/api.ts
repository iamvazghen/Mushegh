import { useEffect, useState } from 'react';
export type RecordData = Record<string, unknown>;
export interface HudControlCommand {
  sequence: number; issued_at: string; action: string; canvas?: string; size?: string;
  query?: string; preset?: string; primitive?: string; color?: string;
}
export interface HudControlSnapshot { stream_id: string; sequence: number; commands: HudControlCommand[] }
export interface Snapshot {
  generated: string; assistant: string; owner: string; presence: string;
  objectives: { text: string; project: string; latest: string; awaiting: string[]; updated: string }[];
  working_on: { title: string; elapsed: string; note: string; kind: string }[];
  awaiting_approval: { summary: string; origin: string }[];
  systems: { llm: string; fallbacks: number; brain: string; judgment?: RecordData };
  performance: { uptime_s?: number; turns?: number; tool_calls?: number; tool_errors?: number; llm_p50_ms?: number; llm_p95_ms?: number };
  health: RecordData[]; reliability: RecordData[]; loops: RecordData[];
  turns_trace: RecordData; llm_providers: RecordData[]; unattended: RecordData;
  hud_control: HudControlSnapshot;
}
export const DATA_COVERAGE = {
  shell: ['generated', 'assistant', 'owner', 'presence', 'systems', 'hud_control'],
  goals: ['objectives', 'working_on'], decisions: ['objectives', 'awaiting_approval'], approvals: ['awaiting_approval'],
  agents: ['working_on', 'loops', 'unattended'], security: ['health', 'reliability', 'unattended'],
  diagnostics: ['performance', 'health', 'reliability', 'loops', 'turns_trace', 'llm_providers', 'unattended'],
} as const;
function record(value: unknown): value is RecordData { return !!value && typeof value === 'object' && !Array.isArray(value); }
export function parseSnapshot(value: unknown): Snapshot {
  if (!record(value) || typeof value.generated !== 'string' || !Number.isFinite(Date.parse(value.generated))) throw new Error('Invalid snapshot');
  for (const key of ['assistant', 'owner', 'presence']) if (typeof value[key] !== 'string') throw new Error(`Invalid ${key}`);
  for (const key of ['objectives', 'working_on', 'awaiting_approval', 'health', 'reliability', 'loops', 'llm_providers'])
    if (!Array.isArray(value[key]) || !value[key].every(record)) throw new Error(`Invalid ${key}`);
  for (const key of ['systems', 'performance', 'turns_trace', 'unattended', 'hud_control']) if (!record(value[key])) throw new Error(`Invalid ${key}`);
  for (const o of value.objectives as RecordData[]) if (typeof o.text !== 'string' || !Array.isArray(o.awaiting) || !o.awaiting.every(x => typeof x === 'string')) throw new Error('Invalid objective');
  for (const a of value.awaiting_approval as RecordData[]) if (typeof a.summary !== 'string' || typeof a.origin !== 'string') throw new Error('Invalid approval');
  const control = value.hud_control as RecordData;
  if (typeof control.stream_id !== 'string' || !Number.isInteger(control.sequence) || !Array.isArray(control.commands) ||
    !control.commands.every(command => record(command) && Number.isInteger(command.sequence) && typeof command.issued_at === 'string' && typeof command.action === 'string')) throw new Error('Invalid hud_control');
  return value as unknown as Snapshot;
}
export const apiPath = (path: string) => import.meta.env.DEV || location.port === '5174' ? `/api/${path}` : `/${path}`;
export function useSnapshot() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState<'connecting' | 'live' | 'offline' | 'stale' | 'auth'>('connecting');
  const [retry, setRetry] = useState(0);
  const [history, setHistory] = useState<{ time: string; latency: number }[]>([]);
  useEffect(() => {
    let stopped = false, timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      if (document.hidden) { timer = setTimeout(poll, 5000); return; }
      try {
        const token = (window as Window & { MUSHEGH_TOKEN?: string }).MUSHEGH_TOKEN;
        const response = await fetch(apiPath('hud.json'), { cache: 'no-store', signal: AbortSignal.any([controller.signal, AbortSignal.timeout(6000)]), headers: token ? { Authorization: `Bearer ${token}` } : {} });
        if (!response.ok) { if (!stopped) setStatus(response.status === 401 ? 'auth' : 'offline'); }
        else {
          const next = parseSnapshot(await response.json());
          if (!stopped) {
            setSnapshot(next);
            const age = Date.now() - Date.parse(next.generated);
            setStatus(age > 30000 || age < -30000 ? 'stale' : 'live');
            if (Number.isFinite(next.performance.llm_p50_ms)) setHistory(prev => [...prev, { time: new Date().toLocaleTimeString(), latency: next.performance.llm_p50_ms! }].slice(-40));
          }
        }
      } catch { if (!stopped) setStatus('offline'); }
      if (!stopped) timer = setTimeout(poll, 5000);
    }
    void poll();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, [retry]);
  return { snapshot, status, history, reconnect: () => { setStatus('connecting'); setRetry(v => v + 1); } };
}

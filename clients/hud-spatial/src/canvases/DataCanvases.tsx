import { useState } from 'react';
import { ArrowUpRight, Check, Circle, LockKeyhole, RefreshCw } from 'lucide-react';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import type { Snapshot } from '../api';
import { apiPath } from '../api';
import { CanvasLoader, Empty } from '../components';

export function Conversation() {
  return <div className="conversation"><div className="conversation-intro"><span className="mono accent">OPENWATARI / OPERATOR LINK</span><h3>A place to think<br/>out loud.</h3><p>Your conversation, references and work.<br/>One continuous workspace.</p></div><div className="connection-note"><span className="status-dot"/><div><strong>Waiting for a transcript stream</strong><p>The spatial shell is ready. Connect the voice event source to see your conversation here.</p></div></div><div className="conversation-foot mono"><span>TRANSCRIPT OFFLINE</span><span>MEMORY NOT CONNECTED</span></div></div>;
}
export function Goals({ data }: { data: Snapshot | null }) {
  return <div className="canvas-scroll"><div className="section-line"><h3>Active objectives</h3><span className="mono">{data ? String(data.objectives.length).padStart(2, '0') : '—'}</span></div>
    {!data ? <Empty title="Your next move, in view" icon="target"><p>Connect the brain to see objectives and their latest progress.</p></Empty> : data.objectives.length === 0 ? <Empty title="No active objectives" icon="target"><p>Set a goal through your assistant to track it here.</p></Empty> : data.objectives.map((o, i) => <article className="objective" key={`${o.text}-${i}`}><div className="objective-index mono">{String(i + 1).padStart(2, '0')}</div><div><span className="mono accent">{o.project || 'GENERAL'}</span><h4>{o.text}</h4><p>{o.latest}</p>{o.awaiting.map((a, j) => <p className="warning" key={j}>Awaiting: {a}</p>)}</div><ArrowUpRight size={16}/></article>)}
    {!!data?.working_on.length && <><h3 className="section-line">Working now</h3>{data.working_on.map((t, i) => <div className="data-row" key={i}><div><strong>{t.title}</strong><p>{t.note}</p></div><span className="mono">{t.elapsed}</span></div>)}</>}
  </div>;
}
function Records({ title, value }: { title: string; value: unknown }) {
  return <details className="record-details"><summary>{title}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>;
}
export function Diagnostics({ data, history, reduced, refresh }: { data: Snapshot | null; history: { time: string; latency: number }[]; reduced: boolean; refresh: () => void }) {
  const p = data?.performance;
  const [review, setReview] = useState<unknown>(null), [reviewError, setReviewError] = useState(''), [loading, setLoading] = useState(false);
  async function loadReview() {
    setLoading(true); setReviewError('');
    try {
      const token = (window as Window & { AFON_TOKEN?: string }).AFON_TOKEN;
      const r = await fetch(apiPath('review.json'), { headers: token ? { Authorization: `Bearer ${token}` } : {}, signal: AbortSignal.timeout(6000), cache: 'no-store' });
      if (!r.ok) throw new Error();
      setReview(await r.json());
    } catch { setReviewError('Review unavailable. Reconnect the brain and retry.'); } finally { setLoading(false); }
  }
  return <div className="canvas-scroll"><div className="metrics-grid">{[['Turns', p?.turns, ''], ['Tool calls', p?.tool_calls, ''], ['Median latency', p?.llm_p50_ms, 'ms'], ['Tool errors', p?.tool_errors, '']].map(([label, value, unit]) => <div className="metric" key={label}><span>{label}</span><strong>{typeof value === 'number' ? Math.round(value).toLocaleString() : '—'}<small>{value !== undefined && unit}</small></strong></div>)}</div>
    <div className="chart-heading mono"><span>LLM ROUTE / P50</span><span>{history.length ? `${history.length} SAMPLES` : 'AWAITING SIGNAL'}</span></div>
    <div className="chart">{history.length > 1 ? <ResponsiveContainer width="100%" height="100%"><AreaChart data={history}><XAxis dataKey="time" hide/><Tooltip contentStyle={{ background: 'var(--color-surface)', borderColor: 'var(--color-line)', color: 'var(--color-text)' }}/><Area dataKey="latency" type="monotone" stroke="var(--color-accent)" fill="var(--color-accent-soft)" isAnimationActive={!reduced} /></AreaChart></ResponsiveContainer> : <div className="chart-wait"><span/><p>{data ? 'Collecting measured samples' : 'No telemetry connection'}</p></div>}</div>
    <div className="data-row"><span>CPU · GPU · VRAM · network</span><span className="mono muted">NOT EXPOSED</span></div>
    {!data && <button className="text-button" onClick={refresh}><RefreshCw size={14}/>Retry connection</button>}
    {data && <><Records title="Jev decision layer" value={data.systems.judgment || { available: false, outcome: 'not exposed' }}/><Records title="Component health" value={data.health}/><Records title="Provider health" value={data.llm_providers}/><Records title="Background loops" value={data.loops}/><Records title="Tool reliability" value={data.reliability}/><Records title="Turn trace & token accounting" value={data.turns_trace}/><Records title="Unattended work & remaining budget" value={data.unattended}/><Records title="All performance values" value={data.performance}/><button onClick={loadReview} disabled={loading} aria-busy={loading}>{loading ? 'Loading review' : 'Review unattended work'}</button>{loading && <CanvasLoader compact label="Loading unattended review" detail="Reading the audited run projection"/>}{reviewError && <p role="alert" className="error">{reviewError}</p>}{review !== null && <Records title="Unattended review details" value={review}/>}</>}
  </div>;
}

export function Agents({ data }: { data: Snapshot | null }) {
  if (!data) return <Empty title="Agent activity unavailable" icon="network"><p>Connect the brain to read active work, declared loops, and unattended runs.</p></Empty>;
  const unattended = data.unattended as Record<string, unknown>;
  return <div className="canvas-scroll"><div className="metrics-grid"><div className="metric"><span>Working now</span><strong>{data.working_on.length}</strong></div><div className="metric"><span>Declared loops</span><strong>{data.loops.length}</strong></div><div className="metric"><span>Unattended runs</span><strong>{typeof unattended.runs === 'number' ? unattended.runs : '—'}</strong></div><div className="metric"><span>Needs attention</span><strong>{typeof unattended.needs_attention === 'number' ? unattended.needs_attention : '—'}</strong></div></div>
    <div className="section-line"><h3>Active work</h3><span className="mono">REAL SNAPSHOT</span></div>
    {data.working_on.length ? data.working_on.map((task, index) => <div className="data-row" key={`${task.title}-${index}`}><div><strong>{task.title}</strong><p>{task.note || task.kind}</p></div><span className="mono">{task.elapsed}</span></div>) : <Empty title="No active delegated work" icon="network"><p>The brain reported no active tasks in this snapshot.</p></Empty>}
    <Records title="Declared background loops" value={data.loops}/><Records title="Unattended work" value={data.unattended}/>
  </div>;
}

export function Security({ data }: { data: Snapshot | null }) {
  if (!data) return <Empty title="Operational risk unavailable" icon="shield"><p>Connect the brain to read component health, reliability, and unattended attention signals.</p></Empty>;
  const unattended = data.unattended as Record<string, unknown>;
  const unhealthy = data.health.filter(item => item.ok === false).length;
  return <div className="canvas-scroll"><div className="metrics-grid"><div className="metric"><span>Unhealthy checks</span><strong>{unhealthy}</strong></div><div className="metric"><span>Flaky tools</span><strong>{data.reliability.length}</strong></div><div className="metric"><span>Needs attention</span><strong>{typeof unattended.needs_attention === 'number' ? unattended.needs_attention : '—'}</strong></div><div className="metric"><span>Network feed</span><strong>—</strong></div></div>
    <p className="source-caveat">This is real operational evidence from Afon. It is not a firewall or threat feed.</p>
    <Records title="Component health" value={data.health}/><Records title="Tool reliability" value={data.reliability}/><Records title="Unattended review headline" value={data.unattended}/>
  </div>;
}
export function Decisions({ data, approvals = false }: { data: Snapshot | null; approvals?: boolean }) {
  const pending = data?.awaiting_approval || [];
  return <div className="canvas-scroll"><div className="section-line"><h3>{approvals ? 'Awaiting your approval' : 'Decisions to revisit'}</h3><LockKeyhole size={16}/></div>
    {!data ? <Empty title="Decision source offline" icon="shield"><p>Pending requests appear when the brain is connected.</p></Empty> : !pending.length && !data.objectives.some(o => o.awaiting.length) ? <Empty title="Nothing awaiting you" icon="shield"><p>New decisions and approval requests will appear here.</p></Empty> : <>
      {!approvals && data.objectives.flatMap((o, i) => o.awaiting.map((a, j) => <div className="data-row" key={`${i}-${j}`}><Circle size={14}/><div><strong>{a}</strong><p>{o.text}</p></div></div>))}
      {pending.map((a, i) => <article className="approval" key={i}><span className="mono warning">{a.origin}</span><h4>{a.summary}</h4><div className="button-row"><button disabled><Check size={14}/>Approve</button><button disabled>Reject</button></div></article>)}
    </>}
    <p className="footnote">Approval actions require a stable request ID and the brain’s authorization endpoint. Use the existing assistant approval flow for now.</p>
  </div>;
}

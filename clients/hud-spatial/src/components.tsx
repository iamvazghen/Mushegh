import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Activity, AudioLines, Box, CalendarDays, Camera, ChartNoAxesCombined, Code2, FileText, Globe2, Hexagon, House, ListTodo, MessagesSquare, Network, ShieldCheck, Target, Unplug } from 'lucide-react';
const icons = { activity: Activity, audio: AudioLines, box: Box, calendar: CalendarDays, camera: Camera, chart: ChartNoAxesCombined, code: Code2, file: FileText, globe: Globe2, home: House, list: ListTodo, messages: MessagesSquare, network: Network, shield: ShieldCheck, target: Target };
export function CanvasIcon({ name, size = 18 }: { name: string; size?: number }) { const Icon = icons[name as keyof typeof icons] || Activity; return <Icon size={size} strokeWidth={1.5} />; }
export function Empty({ title, children, icon = 'activity' }: { title: string; children: ReactNode; icon?: string }) {
  return <div className="empty-state"><div className="empty-symbol"><CanvasIcon name={icon} size={32} /></div><h3>{title}</h3><div className="muted">{children}</div></div>;
}
export function CanvasLoader({ label, detail = 'Waiting for the current operation', compact = false }: { label: string; detail?: string; compact?: boolean }) {
  return <div className={`canvas-loader ${compact ? 'is-compact' : ''}`} role="status" aria-live="polite">
    <div className="loader-grid" aria-hidden="true"><span/></div>
    <div className="loader-core" aria-hidden="true"><Hexagon/><span/></div>
    <div><strong>{label}</strong><small>{detail}</small></div>
  </div>;
}
export class CanvasBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(_error: Error, _info: ErrorInfo) { /* Keep renderer failures isolated; never log local document contents. */ }
  render() { return this.state.failed ? <div className="empty-state"><Unplug /><h3>This canvas could not render</h3><p>Other canvases are still available.</p><button onClick={() => this.setState({ failed: false })}>Retry canvas</button></div> : this.props.children; }
}

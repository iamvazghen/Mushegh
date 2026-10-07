import { useEffect, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { ChevronLeft, ChevronRight, Upload } from 'lucide-react';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { CanvasLoader, Empty } from '../components';
pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString();
const escapeHTML = (s: string) => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
export default function PdfCanvas({ active }: { active: boolean }) {
  const [file, setFile] = useState<File | null>(null), [page, setPage] = useState(1), [pages, setPages] = useState(0), [query, setQuery] = useState(''), [error, setError] = useState('');
  const host = useRef<HTMLDivElement>(null); const [width, setWidth] = useState(400);
  useEffect(() => { const el = host.current; if (!el) return; const observer = new ResizeObserver(([entry]) => { if (entry.contentRect.width > 0) setWidth(entry.contentRect.width); }); observer.observe(el); return () => observer.disconnect(); }, []);
  function highlight({ str }: { str: string }) {
    if (!query.trim()) return escapeHTML(str);
    const needle = query.trim().toLocaleLowerCase(), lower = str.toLocaleLowerCase();
    let start = 0, at: number, result = '';
    while ((at = lower.indexOf(needle, start)) !== -1) { result += escapeHTML(str.slice(start, at)) + '<mark>' + escapeHTML(str.slice(at, at + needle.length)) + '</mark>'; start = at + needle.length; }
    return result + escapeHTML(str.slice(start));
  }
  return <div className="pdf-view"><div className="canvas-toolbar"><label className="file-button"><Upload size={14}/>Open PDF<input type="file" accept="application/pdf" onChange={e => { const f = e.target.files?.[0]; if (f && f.size <= 50 * 1024 * 1024) { setFile(f); setPage(1); setPages(0); setError(''); } else if (f) setError('Choose a PDF smaller than 50 MB.'); }}/></label><span className="truncate mono">{file?.name || 'Local files stay in your browser'}</span></div>
    {file && <div className="pdf-search"><label>Highlight on page<input aria-label="Highlight on page" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search phrase"/></label><div className="button-row"><button aria-label="Previous page" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft size={16}/></button><label className="page-number"><span className="sr-only">Page number</span><input type="number" min={1} max={pages || 1} value={page} onChange={e => setPage(Math.max(1, Math.min(pages || 1, Number(e.target.value) || 1)))}/></label><span className="mono">/ {pages || '—'}</span><button aria-label="Next page" disabled={page >= pages} onClick={() => setPage(p => p + 1)}><ChevronRight size={16}/></button></div></div>}
    {error && <p role="alert" className="error">{error}</p>}
    <div className="pdf-page canvas-scroll" ref={host}>{file ? active && <Document file={file} onLoadSuccess={({ numPages }) => setPages(numPages)} onLoadError={() => setError('This PDF could not be read. Try another file.')} loading={<CanvasLoader label="Reading local PDF" detail="Indexing pages in this browser"/>}><Page pageNumber={page} width={Math.max(180, width - 32)} devicePixelRatio={Math.min(devicePixelRatio, 1.5)} customTextRenderer={highlight} renderAnnotationLayer={false} loading={<CanvasLoader label={`Rendering page ${page}`} detail="Preparing text and vector layers"/>} /></Document> : <Empty title="Bring a reference into view" icon="file"><p>Open a local PDF. Jump between pages and highlight text while keeping the conversation alongside.</p></Empty>}</div>
  </div>;
}

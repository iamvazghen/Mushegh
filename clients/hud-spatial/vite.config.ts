import { defineConfig, loadEnv, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';

// Only these reads may cross the dev proxy. Root credentials stay in Node.
function brainReads(env: Record<string, string>): Plugin {
  const target = env.HUD_BRAIN_ORIGIN || `http://127.0.0.1:${env.AFON_CLIENT_HTTP_PORT || '8766'}`;
  const allowed = new Set(['/hud.json', '/review.json']);
  const attach: NonNullable<Plugin['configureServer']> = server => {
    server.middlewares.use('/api', async (req, res) => {
      const path = req.url?.split('?')[0] || '';
      if (req.method !== 'GET' || !allowed.has(path)) {
        res.writeHead(404).end(); return;
      }
      res.setHeader('Cache-Control', 'no-store');
      try {
        const upstream = await fetch(new URL(path, target), {
          headers: env.AFON_API_AUTH_TOKEN ? { Authorization: `Bearer ${env.AFON_API_AUTH_TOKEN}` } : {},
          signal: AbortSignal.timeout(4000), redirect: 'error',
        });
        if (!upstream.ok) {
          res.writeHead(upstream.status, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: upstream.status === 401 ? 'Brain authentication failed' : 'Brain request failed' }));
          return;
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(await upstream.json()));
      } catch {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Brain unavailable. Spatial controls and local files still work.' }));
      }
    });
  };
  return { name: 'brain-read-proxy', configureServer: attach, configurePreviewServer: attach as Plugin['configurePreviewServer'] };
}

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, fileURLToPath(new URL('../../', import.meta.url)), ['AFON_', 'HUD_']), ...process.env } as Record<string, string>;
  return {
    base: './', plugins: [react(), tailwind(), brainReads(env)],
    server: { host: '127.0.0.1', port: 5173, strictPort: true, fs: { strict: true } },
    preview: { host: '127.0.0.1', port: 5174, strictPort: true },
    build: { target: 'es2022' },
  };
});

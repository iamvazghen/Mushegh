import { describe, expect, it } from 'vitest';
import { EMBED_HOSTS, decideFrame, decideMedia, isDiskPath, narrowFeatures, toEmbedUrl } from './embedPolicy';

const BASE = 'http://127.0.0.1:5173/';
const ok = (r: ReturnType<typeof decideFrame>) => r.allow === true ? r.url : `BLOCKED:${r.allow === false ? r.reason : ''}`;

describe('framing policy', () => {
  it('allows the three embed shapes it exists for', () => {
    expect(ok(decideFrame('https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ', BASE))).toContain('youtube-nocookie.com/embed/dQw4w9WgXcQ');
    expect(ok(decideFrame('https://player.vimeo.com/video/76979871', BASE))).toContain('vimeo.com/video/76979871');
  });

  it('rewrites a watch URL into the cookieless embed form', () => {
    expect(ok(decideFrame('https://www.youtube.com/watch?v=dQw4w9WgXcQ', BASE))).toContain('youtube-nocookie.com/embed/dQw4w9WgXcQ');
    expect(ok(decideFrame('https://youtu.be/dQw4w9WgXcQ', BASE))).toContain('youtube-nocookie.com/embed/dQw4w9WgXcQ');
  });

  it('refuses a host that is not on the list, whatever the path', () => {
    expect(ok(decideFrame('https://evil.example/embed/x', BASE))).toBe('BLOCKED:host-not-allowed');
    // Right shape, wrong host — the shape must not be what grants permission.
    expect(ok(decideFrame('https://youtube.com.evil.example/embed/dQw4w9WgXcQ', BASE))).toBe('BLOCKED:host-not-allowed');
  });

  it('refuses a listed host on a path it does not serve', () => {
    expect(ok(decideFrame('https://www.youtube-nocookie.com/../../../etc/passwd', BASE))).toBe('BLOCKED:path-not-allowed');
    expect(ok(decideFrame('https://player.vimeo.com/video/abc', BASE))).toBe('BLOCKED:path-not-allowed');
  });

  it('refuses a javascript: src even though it parses as a URL', () => {
    // It has no host at all, so the refusal must not be reported as an unknown
    // one — the caller would go looking at the host list.
    expect(ok(decideFrame('javascript:alert(1)', BASE))).toBe('BLOCKED:scheme-not-allowed');
    expect(ok(decideFrame('data:text/html,<script>alert(1)</script>', BASE))).toBe('BLOCKED:scheme-not-allowed');
  });

  it('refuses an unparseable src rather than guessing', () => {
    expect(ok(decideFrame('http://', BASE))).toBe('BLOCKED:unparseable');
  });

  it('refuses a protocol-relative src that resolves off-host', () => {
    expect(ok(decideFrame('//evil.example/embed/x', BASE))).toBe('BLOCKED:host-not-allowed');
  });

  it('refuses a relative src, which resolves to this client itself', () => {
    expect(ok(decideFrame('/hud-spatial/dist/index.html', BASE))).toBe('BLOCKED:host-not-allowed');
  });

  it('rejects an embed id of the wrong shape instead of trimming it', () => {
    expect(toEmbedUrl(new URL('https://youtu.be/../evil'))).toBeNull();
    expect(toEmbedUrl(new URL('https://www.youtube.com/watch?v=a'))).toBeNull();
  });

  it('pins every allowed host to a bounded path', () => {
    for (const [host, shape] of Object.entries(EMBED_HOSTS)) {
      expect(shape.test('https://' + host)).toBe(false);
      expect(host).toMatch(/^[a-z0-9.-]+$/);
    }
  });
});

describe('iframe feature policy', () => {
  it('keeps an explicitly allowed feature', () => {
    expect(narrowFeatures('autoplay; encrypted-media')).toBe('autoplay; encrypted-media');
  });

  it('drops the camera, the microphone and geolocation', () => {
    // An embed that could hold a camera open behind a backgrounded tile is the
    // failure this client cannot afford on this host.
    expect(narrowFeatures('camera; microphone; geolocation; autoplay')).toBe('autoplay');
  });

  it('drops a wildcard rather than treating it as a feature name', () => {
    expect(narrowFeatures("camera 'none'; autoplay *")).toBe('autoplay');
  });

  it('trims a trailing space left by stripping a wildcard', () => {
    expect(narrowFeatures('autoplay *')).toBe('autoplay');
  });

  it('reduces anything unrecognised to nothing', () => {
    expect(narrowFeatures('xr-spatial-tracking; fullscreen')).toBe('fullscreen');
    expect(narrowFeatures(null)).toBe('');
    expect(narrowFeatures(';;;')).toBe('');
  });

  it('is case and whitespace insensitive', () => {
    expect(narrowFeatures('  CAMERA ;  Autoplay  ')).toBe('autoplay');
  });
});

describe('disk path detection', () => {
  it('recognises the macOS and Linux roots', () => {
    expect(isDiskPath('/Users/iamva/shots/a.png')).toBe(true);
    expect(isDiskPath('/tmp/a.png')).toBe(true);
  });

  it('recognises a Windows absolute path, which the source regex missed', () => {
    expect(isDiskPath('C:\\Users\\iamva\\shots\\a.png')).toBe(true);
    expect(isDiskPath('D:/data/a.png')).toBe(true);
    expect(isDiskPath('file:///C:/Users/iamva/a.png')).toBe(true);
  });

  it('leaves an app-relative asset alone', () => {
    // Rewriting these would turn the client's own images into host file reads.
    expect(isDiskPath('/assets/logo.svg')).toBe(false);
    expect(isDiskPath('./logo.svg')).toBe(false);
    expect(isDiskPath('logo.svg')).toBe(false);
  });
});

describe('media routing', () => {
  it('sends a disk path to the local route and a remote URL to the proxy', () => {
    expect(decideMedia('C:\\Users\\iamva\\a.png')).toEqual({ kind: 'disk', path: 'C:\\Users\\iamva\\a.png' });
    expect(decideMedia('https://cdn.example/a.png')).toEqual({ kind: 'remote', url: 'https://cdn.example/a.png' });
  });

  it('leaves a page-local source entirely alone', () => {
    // Nothing leaves the page for these, so there is nothing to proxy.
    expect(decideMedia('data:image/png;base64,AAAA')).toEqual({ kind: 'local' });
    expect(decideMedia('/assets/logo.svg')).toEqual({ kind: 'local' });
    expect(decideMedia('')).toEqual({ kind: 'local' });
  });

  it('does not treat an ftp source as remote http', () => {
    expect(decideMedia('ftp://example/a.png')).toEqual({ kind: 'local' });
  });
});
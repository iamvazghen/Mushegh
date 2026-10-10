/**
 * What this client is allowed to frame, load, and hand a camera to.
 *
 * The `browser` canvas is a future surface, and when it lands it will be the
 * first place in this client that renders a URL someone else chose. That makes
 * the decision about *which* URLs worth a policy, and it belongs in one tested
 * module rather than inline at the call site: a second surface with a slightly
 * looser host list is a hole with a changelog.
 *
 * Ported from adewaskar/jarvis `src/ui/sanitise.ts` (MIT, © 2026 Aditya
 * Dewaskar), minus the parts that only make sense with a proxy bridge behind it.
 * Everything here is a pure function over a URL, so it is testable without a
 * browser and usable by whichever surface needs it.
 */

/**
 * Hosts this client will frame, each with the path shape it accepts.
 *
 * A closed list, not a pattern: an iframe is the one way to play an embed inline
 * — those providers will not hand over the media file — and there is no unknown
 * host worth framing. Everything else is removed rather than filtered.
 */
export const EMBED_HOSTS: Readonly<Record<string, RegExp>> = {
  'www.youtube-nocookie.com': /^\/embed\/[\w-]+$/,
  'www.youtube.com': /^\/embed\/[\w-]+$/,
  'player.vimeo.com': /^\/video\/\d+$/,
};

/** Eleven characters in practice; bounded rather than exact, in case that moves. */
const YT_ID = /^[\w-]{6,20}$/;

/** Eleven characters in practice, and no more — a bound, not an exact length. */
const VIMEO_ID = /^\d{1,20}$/;

/**
 * Search results hand back `youtube.com/watch?v=ID` and `youtu.be/ID`, so that
 * is what a caller is likely to be holding. Refusing those would mean showing
 * nothing, so they are rewritten into the cookieless embed form instead.
 */
export function toEmbedUrl(url: URL): URL | null {
  const host = url.hostname.toLowerCase().replace(/^(?:www|m|music)\./, '');
  let id = '';
  if (host === 'youtube.com' && url.pathname === '/watch') id = url.searchParams.get('v') ?? '';
  else if (host === 'youtu.be') id = url.pathname.slice(1);
  if (!YT_ID.test(id)) return null;
  return new URL(`https://www.youtube-nocookie.com/embed/${id}`);
}

export type FrameDecision =
  | { allow: true; url: string }
  | { allow: false; reason: string };

/**
 * Decide whether a src may be framed, and normalise it if so.
 *
 * Anything that fails to parse, resolves to a host that is not on the list, or
 * points at a path that host does not serve is refused with a reason rather than
 * silently dropped — a caller that renders "embed unavailable" needs to know
 * whether it was blocked or merely absent.
 */
export function decideFrame(raw: string, base: string): FrameDecision {
  let url: URL;
  try {
    // Resolved against the page so a relative or protocol-relative src cannot
    // slip past the host test by never being parsed at all.
    url = new URL(raw, base);
  } catch {
    return { allow: false, reason: 'unparseable' };
  }
  const embed = toEmbedUrl(url) ?? url;
  // Scheme, then host, then a downgrade check — in that order, so each refusal
  // names the thing that actually caused it. `javascript:` has no host at all,
  // and reporting it as an unrecognised host would point the caller at the wrong
  // rule; an http:// src that would otherwise be allowed is a downgrade, which
  // is a different problem from an off-host src.
  if (embed.protocol !== 'https:' && embed.protocol !== 'http:') {
    return { allow: false, reason: 'scheme-not-allowed' };
  }
  const shape = EMBED_HOSTS[embed.hostname.toLowerCase()];
  if (!shape) return { allow: false, reason: 'host-not-allowed' };
  if (embed.protocol !== 'https:') return { allow: false, reason: 'not-https' };
  if (!shape.test(embed.pathname)) return { allow: false, reason: 'path-not-allowed' };
  return { allow: true, url: embed.toString() };
}

/**
 * Camera, microphone and geolocation are excluded from the feature policy
 * deliberately.
 *
 * An embed that could ask for a camera could hold it open behind a tile you
 * backgrounded, on a machine whose whole premise is that its owner knows where
 * its cameras are pointed. The cost of dropping them is a Vimeo embed that
 * cannot record — which is not a use this client has.
 */
const FORBIDDEN_FEATURES = ['camera', 'microphone', 'geolocation', 'display-capture', 'clipboard-read', 'clipboard-write'];

/** Features an embed may have. Everything else is dropped. */
const ALLOWED_FEATURES = new Set(['accelerometer', 'autoplay', 'encrypted-media', 'gyroscope', 'picture-in-picture', 'fullscreen']);

/**
 * Reduce an `allow` attribute to the safe subset.
 *
 * DOMPurify and every sanitiser that matters will let `allow` through verbatim
 * — it is a plain string on an attribute nobody thinks of as a capability — so
 * the narrowing has to happen explicitly.
 */
export function narrowFeatures(raw: string | null): string {
  const kept = (raw ?? '')
    .split(';')
    .map(s => s.trim().toLowerCase())
    .filter(s => s.length > 0)
    .filter(s => !FORBIDDEN_FEATURES.some(f => s.includes(f)))
    .filter(s => [...ALLOWED_FEATURES].some(f => s.includes(f)))
    // Trimmed again after the rewrites: `autoplay *` becomes `autoplay ` and a
    // trailing space would ride out into the attribute we emit.
    .map(s => s.replace(/^allow[- ]/, '').replace(/\*.*$/, '').trim())
    .filter(s => s.length > 0);
  return [...new Set(kept)].join('; ');
}

/**
 * Paths that are genuinely on this machine's disk, as opposed to app-relative
 * URLs that happen to begin with a slash.
 *
 * The source this is ported from recognises macOS and Linux roots only, which
 * on this host would classify nothing — every absolute Windows path would fall
 * through and be treated as an app-relative URL. Both shapes are recognised,
 * and a drive-letter path is only ever a disk path.
 */
const DISK_PATH_UNIX = /^\/(Users|home|root|Volumes|Applications|System|Library|private|tmp|var|opt|mnt|media|srv|data|etc)\//;
const DISK_PATH_WINDOWS = /^[A-Za-z]:[\\/]/;

/**
 * Strip a `file://` scheme, keeping the path in the shape it had on disk.
 *
 * A `file:` URL carries a slash for the authority that a bare path does not, so
 * `file:///Users/x` strips to `/Users/x` but `file:///C:/x` must strip to `C:/x` —
 * otherwise the drive-letter test never sees a drive letter and every absolute
 * Windows path reads as an app-relative URL.
 */
function stripFileScheme(raw: string): string {
  if (!/^file:\/\//i.test(raw)) return raw;
  const rest = raw.slice('file://'.length);
  return /^\/[A-Za-z]:[\\/]/.test(rest) ? rest.slice(1) : rest;
}

export function isDiskPath(raw: string): boolean {
  const path = stripFileScheme(raw);
  return DISK_PATH_UNIX.test(path) || DISK_PATH_WINDOWS.test(path);
}

/**
 * Classify a media source without fetching it.
 *
 * The three destinations want different handling: a disk path is a local file
 * the browser cannot reach directly, a remote http(s) URL is somebody else's
 * server and must never be contacted from this page, and everything else
 * (data:, blob:, app-relative) already stays inside the page and so needs
 * nothing.
 */
export type MediaDecision =
  | { kind: 'disk'; path: string }
  | { kind: 'remote'; url: string }
  | { kind: 'local' };

export function decideMedia(raw: string): MediaDecision {
  if (!raw) return { kind: 'local' };
  if (isDiskPath(raw)) return { kind: 'disk', path: raw.replace(/^file:\/\//, '') };
  if (/^https?:\/\//i.test(raw)) return { kind: 'remote', url: raw };
  return { kind: 'local' };
}
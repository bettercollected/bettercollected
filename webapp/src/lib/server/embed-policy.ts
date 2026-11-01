/**
 * Which sites may show a workspace's forms in a frame (docs/embed.md): the webapp's proxy asks the
 * backend (`GET /workspaces/embed/policy`, public) and answers each respondent form page with a
 * `Content-Security-Policy: frame-ancestors ...`. Only while the server's FORM_EMBED_ENABLED is on; while
 * it is off the answer says so and the pages carry no framing header, as before.
 */
import environments from '@app/configs/environments';

export interface EmbedPolicy {
    enabled: boolean;
    origins: string[];
}

/** Exactly one of these names the workspace. */
export type PolicyQuery = { workspace_name: string } | { custom_domain: string } | { workspace_id: string };

const CACHE_MS = 30_000;
const FAILURE_CACHE_MS = 5_000;
const CACHE_LIMIT = 500;
const TIMEOUT_MS = 2_000;

const cache = new Map<string, { at: number; policy: EmbedPolicy | null }>();

export function clearEmbedPolicyCache() {
    cache.clear();
}

/** The policy of the workspace, kept for 30 s; null when the backend cannot be asked (kept for 5 s). */
export async function fetchEmbedPolicy(query: PolicyQuery, now: number = Date.now(), fetcher: typeof fetch = fetch): Promise<EmbedPolicy | null> {
    const params = new URLSearchParams(query as Record<string, string>);
    const key = params.toString();
    const hit = cache.get(key);
    if (hit && now - hit.at < (hit.policy ? CACHE_MS : FAILURE_CACHE_MS)) return hit.policy;
    let policy: EmbedPolicy | null = null;
    try {
        const response = await fetcher(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/embed/policy?${key}`, { cache: 'no-store', signal: AbortSignal.timeout(TIMEOUT_MS) });
        if (response.ok) {
            const body = await response.json();
            policy = { enabled: body?.enabled === true, origins: Array.isArray(body?.origins) ? body.origins.filter((item: unknown): item is string => typeof item === 'string') : [] };
        }
    } catch {
        policy = null;
    }
    if (cache.size >= CACHE_LIMIT) cache.clear();
    cache.set(key, { at: now, policy });
    return policy;
}

// What the backend stores (services/form_embed.py), checked again here before anything is written into a
// header: scheme://host[:port] with an optional leading "*." and nothing that could add a source or a directive.
const ORIGIN = /^https?:\/\/(\*\.)?[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:[0-9]{1,5})?$/;

/**
 * The `frame-ancestors` value for a respondent form page. `null`: send none (the server's switch is off,
 * so the page is served as before). Otherwise this site, the dashboard (the builder's preview frames the
 * page) and the workspace's allowed sites; with no policy at all (the backend did not answer) just the
 * first two: a failure never opens the page to every site.
 */
export function frameAncestorsValue(policy: EmbedPolicy | null, dashboardOrigin: string): string | null {
    if (policy && !policy.enabled) return null;
    const sources = ["'self'", ...(ORIGIN.test(dashboardOrigin) ? [dashboardOrigin] : [])];
    for (const origin of policy?.origins ?? []) {
        if (ORIGIN.test(origin) && !sources.includes(origin)) sources.push(origin);
    }
    return `frame-ancestors ${sources.join(' ')}`;
}

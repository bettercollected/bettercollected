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
/** After a failed ask, how long before the backend is asked again. */
const RETRY_MS = 5_000;
/** How long a policy that was good is still used while the backend cannot be asked. */
const STALE_MS = 10 * 60_000;
const CACHE_LIMIT = 500;
const TIMEOUT_MS = 2_000;

interface Entry {
    /** The last answer the backend gave for this workspace, and when. */
    good: EmbedPolicy | null;
    goodAt: number;
    /** When the backend was last asked (successfully or not), for the retry delay. */
    askedAt: number;
    failed: boolean;
}

// Least recently used first: an entry is re-inserted when it is read.
const cache = new Map<string, Entry>();
const inFlight = new Map<string, Promise<EmbedPolicy>>();
// Whether the backend has ever said the switch is on, in this process: after that, a failure to ask about a
// workspace nobody asked about yet must not open its forms.
let switchSeenOn = false;

const TRUE_VALUES = new Set(['1', 'true', 'yes', 'on']);

/**
 * What the operator told this webapp about the server's switch (its own runtime environment variable
 * `FORM_EMBED_ENABLED`, the same name and values as the backend's, read on every request). It decides only
 * the case where nothing is known yet (a fresh webapp whose first ask failed): on means strict, unset or off
 * means no header, as before the feature, so a webapp rolled out before its backend, or with the switch off,
 * changes nothing. Whenever the backend answers, its answer is the truth, per workspace.
 */
export function embedSwitchHint(): boolean {
    return TRUE_VALUES.has((process.env.FORM_EMBED_ENABLED ?? '').trim().toLowerCase());
}

const OFF: EmbedPolicy = { enabled: false, origins: [] };
/** Nobody may frame it but this site and the dashboard. */
const STRICT: EmbedPolicy = { enabled: true, origins: [] };

export function clearEmbedPolicyCache() {
    cache.clear();
    inFlight.clear();
    switchSeenOn = false;
}

function remember(key: string, entry: Entry) {
    cache.delete(key);
    cache.set(key, entry);
    while (cache.size > CACHE_LIMIT) {
        const oldest = cache.keys().next().value;
        if (oldest === undefined) break;
        cache.delete(oldest);
    }
}

/**
 * The policy of the workspace. Kept 30 s; asked once at a time per workspace.
 *
 * - The backend says what the switch is: `enabled: false` means no header, as before the feature.
 * - A 404 or 405 means this backend has no such route yet (the webapp was rolled out first): the same as off.
 * - A failure (5xx, 429, a timeout, no connection) never changes what was last known: the last good answer is
 *   used (up to 10 minutes), and that is also the fail-closed case, because it names the sites of a workspace
 *   that had the switch on. With no last answer the strict policy is used if the backend has ever said the
 *   switch is on in this process or the operator says so in this webapp's own environment (`embedSwitchHint`,
 *   which covers a cold start with the backend down); otherwise no header, so a rollout order or an outage
 *   of the backend alone changes nothing for embeds that work today.
 */
export async function fetchEmbedPolicy(query: PolicyQuery, now: number = Date.now(), fetcher: typeof fetch = fetch): Promise<EmbedPolicy> {
    const key = new URLSearchParams(query as Record<string, string>).toString();
    const hit = cache.get(key);
    if (hit) {
        if (hit.good && !hit.failed && now - hit.askedAt < CACHE_MS) {
            remember(key, hit);
            return hit.good;
        }
        if (hit.failed && now - hit.askedAt < RETRY_MS) {
            remember(key, hit);
            return staleOrDefault(hit, now);
        }
    }
    const pending = inFlight.get(key);
    if (pending) return pending;
    const request = ask(key, hit, now, fetcher).finally(() => inFlight.delete(key));
    inFlight.set(key, request);
    return request;
}

function staleOrDefault(entry: Entry | undefined, now: number): EmbedPolicy {
    if (entry?.good) {
        if (!entry.good.enabled) return OFF;
        return now - entry.goodAt < STALE_MS ? entry.good : STRICT;
    }
    return switchSeenOn || embedSwitchHint() ? STRICT : OFF;
}

async function ask(key: string, previous: Entry | undefined, now: number, fetcher: typeof fetch): Promise<EmbedPolicy> {
    try {
        const response = await fetcher(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/embed/policy?${key}`, { cache: 'no-store', signal: AbortSignal.timeout(TIMEOUT_MS) });
        if (response.status === 404 || response.status === 405) {
            switchSeenOn = false;
            remember(key, { good: OFF, goodAt: now, askedAt: now, failed: false });
            return OFF;
        }
        if (!response.ok) throw new Error(`policy answered ${response.status}`);
        const body = await response.json();
        const policy: EmbedPolicy = { enabled: body?.enabled === true, origins: Array.isArray(body?.origins) ? body.origins.filter((item: unknown): item is string => typeof item === 'string') : [] };
        switchSeenOn = policy.enabled;
        remember(key, { good: policy, goodAt: now, askedAt: now, failed: false });
        return policy;
    } catch {
        const entry: Entry = { good: previous?.good ?? null, goodAt: previous?.goodAt ?? 0, askedAt: now, failed: true };
        remember(key, entry);
        return staleOrDefault(entry, now);
    }
}

// What the backend stores (services/form_embed.py), checked again here before anything is written into a
// header: scheme://host[:port] with an optional leading "*." and nothing that could add a source or a directive.
const ORIGIN = /^(?:https:\/\/(?:\*\.)?[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?|http:\/\/(?:localhost|127\.0\.0\.1))(?::[0-9]{1,5})?$/;

// The dashboard's own origin comes from this server's settings (any scheme and port).
const DASHBOARD_ORIGIN = /^https?:\/\/[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:[0-9]{1,5})?$/;

/**
 * The `frame-ancestors` value for a respondent form page. `null`: send none (the server's switch is off,
 * so the page is served as before, or this backend does not know the feature yet). Otherwise this site, the dashboard (the builder's preview frames the
 * page) and the workspace's allowed sites; with no policy at all (the backend did not answer) just the
 * first two: a failure never opens the page to every site.
 */
export function frameAncestorsValue(policy: EmbedPolicy | null, dashboardOrigin: string): string | null {
    if (policy && !policy.enabled) return null;
    const sources = ["'self'", ...(DASHBOARD_ORIGIN.test(dashboardOrigin) ? [dashboardOrigin] : [])];
    for (const origin of policy?.origins ?? []) {
        if (ORIGIN.test(origin) && !sources.includes(origin)) sources.push(origin);
    }
    return `frame-ancestors ${sources.join(' ')}`;
}

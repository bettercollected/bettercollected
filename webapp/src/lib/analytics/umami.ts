// Canonical form-view tracking for the self-hosted Umami integration (see
// plans/umami-self-hosted-form-analytics.md). Public forms can be reached via
// the client-host route (`/{workspace}/forms/{slug}`) or a custom domain
// (`/forms/{slug}`) — both must attribute to the same analytics path, so we
// track it explicitly instead of relying on Umami's automatic pageview.
// Automatic tracking is disabled entirely (data-auto-track="false" in
// app/layout.tsx) — it would double-count every form view against this
// explicit event and split the same form across host-specific paths.

export function buildCanonicalFormPath(workspaceName: string, slug: string): string {
    return `/${workspaceName}/forms/${slug}`;
}

type UmamiTracker = {
    track: (payload: (props: Record<string, unknown>) => Record<string, unknown>) => void;
};

function getUmami(): UmamiTracker | undefined {
    if (typeof window === 'undefined') return undefined;
    const umami = (window as unknown as { umami?: UmamiTracker }).umami;
    return umami && typeof umami.track === 'function' ? umami : undefined;
}

function sendCanonicalPageview(umami: UmamiTracker, canonicalUrl: string): void {
    try {
        umami.track((props) => ({ ...props, url: canonicalUrl }));
    } catch {
        // Analytics must never break the form.
    }
}

// The Umami script loads asynchronously (next/script afterInteractive), so the
// form page's mount effect can run before window.umami exists. Since the
// explicit event is the ONLY pageview (auto-track is off), poll briefly for
// the script instead of dropping the view.
const RETRY_INTERVAL_MS = 250;
const MAX_RETRIES = 40; // ~10s — beyond that the script is blocked/unreachable.

export function trackCanonicalFormView(workspaceName: string, slug: string): void {
    if (typeof window === 'undefined' || !workspaceName || !slug) return;

    const canonicalUrl = buildCanonicalFormPath(workspaceName, slug);

    const umami = getUmami();
    if (umami) {
        sendCanonicalPageview(umami, canonicalUrl);
        return;
    }

    let attempts = 0;
    const timer = window.setInterval(() => {
        attempts += 1;
        const tracker = getUmami();
        if (tracker) {
            window.clearInterval(timer);
            sendCanonicalPageview(tracker, canonicalUrl);
        } else if (attempts >= MAX_RETRIES) {
            window.clearInterval(timer);
        }
    }, RETRY_INTERVAL_MS);
}

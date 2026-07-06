// Canonical form-view tracking for the self-hosted Umami integration (see
// plans/umami-self-hosted-form-analytics.md). Public forms can be reached via
// the client-host route (`/{workspace}/forms/{slug}`) or a custom domain
// (`/forms/{slug}`) — both must attribute to the same analytics path, so we
// track it explicitly instead of relying on Umami's automatic pageview.

export function buildCanonicalFormPath(workspaceName: string, slug: string): string {
    return `/${workspaceName}/forms/${slug}`;
}

type UmamiTracker = {
    track: (payload: (props: Record<string, unknown>) => Record<string, unknown>) => void;
};

export function trackCanonicalFormView(workspaceName: string, slug: string): void {
    if (typeof window === 'undefined' || !workspaceName || !slug) return;

    const umami = (window as unknown as { umami?: UmamiTracker }).umami;
    if (!umami || typeof umami.track !== 'function') return;

    const canonicalUrl = buildCanonicalFormPath(workspaceName, slug);
    try {
        umami.track((props) => ({ ...props, url: canonicalUrl }));
    } catch {
        // Analytics must never break the form.
    }
}

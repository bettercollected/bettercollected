/**
 * Inside a frame a link must not take the form's page away from the host page, and a sign-in or the
 * respondent's own submission pages need a first-party window (third-party cookies are not dependable).
 * Every link that leaves the form's own page opens in a new tab instead (docs/embed.md).
 */
export function opensOutside(anchor: Pick<HTMLAnchorElement, 'href' | 'target'>, current: Pick<URL, 'origin' | 'pathname'>): boolean {
    // the author said where it goes (`_blank` for external links already)
    if (anchor.target && anchor.target !== '_self') return false;
    let url: URL;
    try {
        url = new URL(anchor.href);
    } catch {
        return false;
    }
    // mailto:, tel: and in-page anchors are not navigations of the frame
    if (url.protocol !== 'https:' && url.protocol !== 'http:') return false;
    return !(url.origin === current.origin && url.pathname === current.pathname);
}

/** A capture-phase click listener that sends links leaving the page to a new tab. Returns its remover. */
export function guardLinks(doc: Document = document, win: Window = window): () => void {
    const onClick = (event: MouseEvent) => {
        // a modified or non-primary click already opens elsewhere, in the browser's own way
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const anchor = (event.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
        if (!anchor || !opensOutside(anchor, win.location)) return;
        event.preventDefault();
        event.stopPropagation();
        win.open(anchor.href, '_blank', 'noopener,noreferrer');
    };
    doc.addEventListener('click', onClick, true);
    return () => doc.removeEventListener('click', onClick, true);
}

/** Opens `url` in a new tab (what a sign-in does inside a frame). */
export function openOutside(url: string, win: Window = window): void {
    win.open(url, '_blank', 'noopener,noreferrer');
}

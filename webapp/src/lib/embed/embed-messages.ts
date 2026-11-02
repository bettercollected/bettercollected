/**
 * What a framed form page tells the page around it (docs/embed.md, protocol v1). Lifecycle only: that
 * the form loaded, how tall it needs to be (in steps of 40 px) and that it was submitted. No page number or
 * counter (with branching the number of pages seen depends on earlier answers). Never an answer, a field, a
 * response id or any text of the form: the builders below take exactly the fields of each message, so
 * nothing else can ride along.
 */
export const EMBED_SOURCE = 'bettercollected-form';
export const EMBED_VERSION = 1;

export type EmbedMessage =
    | { source: typeof EMBED_SOURCE; v: typeof EMBED_VERSION; type: 'loaded' }
    | { source: typeof EMBED_SOURCE; v: typeof EMBED_VERSION; type: 'height'; height: number }
    | { source: typeof EMBED_SOURCE; v: typeof EMBED_VERSION; type: 'submitted' };

const base = { source: EMBED_SOURCE, v: EMBED_VERSION } as const;

export const loadedMessage = (): EmbedMessage => ({ ...base, type: 'loaded' });
export const heightMessage = (height: number): EmbedMessage => ({ ...base, type: 'height', height });
export const submittedMessage = (): EmbedMessage => ({ ...base, type: 'submitted' });

/**
 * Sends `message` to the page that framed this one, addressed to exactly `parentOrigin` (never `*`).
 * Nothing is sent from a page that is not in a frame or that was given no valid parent origin.
 * Returns whether it was sent.
 */
export function postToParent(message: EmbedMessage, parentOrigin: string | null, win: Window = window): boolean {
    if (!parentOrigin || win.parent === win) return false;
    win.parent.postMessage(message, parentOrigin);
    return true;
}

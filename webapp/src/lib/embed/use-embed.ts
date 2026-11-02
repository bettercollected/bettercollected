'use client';

import { useSyncExternalStore } from 'react';

import { EmbedContext, NOT_EMBEDDED, readEmbedContext } from './embed-params';

// The address is read once on the client (it cannot change while the page is open) and cached, so the
// snapshot is stable; the server and the hydration pass see "not embedded", as the server render does.
let cached: EmbedContext | null = null;

const subscribe = () => () => {};
const clientSnapshot = (): EmbedContext => (cached ??= readEmbedContext(window.location.search));
const serverSnapshot = (): EmbedContext => NOT_EMBEDDED;

/** Whether the respondent page is shown in another site's frame, and which origin that is. */
export function useEmbed(): EmbedContext {
    return useSyncExternalStore(subscribe, clientSnapshot, serverSnapshot);
}

/** For tests: forget the cached address. */
export function resetEmbedContext() {
    cached = null;
}

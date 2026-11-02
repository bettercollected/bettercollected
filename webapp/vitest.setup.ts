// Extends Vitest's `expect` with jest-dom matchers (toBeInTheDocument, etc.)
// and clears the rendered DOM between tests.
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// The dashboard's own words come from translation keys: start the app's i18next (English) for every test file,
// so components render their English text as they do on the page (a test that needs Dutch switches the language).
import '@app/shared/hocs/i18n-provider';

// next/font is resolved by the Next.js compiler at build time.
vi.mock('@app/assets/fonts/leaflet-serif', () => ({ leafletSerif: { className: '', variable: '', style: { fontFamily: "'Source Serif 4'" } } }));
vi.mock('@app/assets/fonts/theme-faces', () => ({
    themeFaces: {
        'atkinson-next': "'Atkinson Hyperlegible Next', ui-sans-serif, system-ui, sans-serif",
        archivo: "'Archivo', ui-sans-serif, system-ui, sans-serif",
        besley: "'Besley', Georgia, 'Times New Roman', serif",
        rubik: "'Rubik', ui-sans-serif, system-ui, sans-serif",
        'atkinson-mono': "'Atkinson Hyperlegible Mono', ui-monospace, monospace"
    }
}));

// A unit test never reaches the network. Left alone, a component that asks the API for something (the store's
// base URL is a real host) sends a real request that can still be in flight when the test file ends. Its
// answer then arrives after Vitest has torn the file's environment down, and RTK Query's middleware throws
// `ReferenceError: process is not defined` as an unhandled rejection, which Vitest pins on whichever file
// happens to be running by then. So the default `fetch` is one that never answers: the request stays pending
// until the caller aborts it, exactly what the component saw while it was waiting for the network. A test that
// needs an answer stubs `fetch` itself (`vi.stubGlobal('fetch', ...)`, `vi.spyOn(globalThis, 'fetch')`).
globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
    new Promise<Response>((_resolve, reject) => {
        const signal = init?.signal ?? (typeof Request !== 'undefined' && input instanceof Request ? input.signal : undefined);
        const abort = () => reject(signal?.reason ?? new DOMException('The operation was aborted.', 'AbortError'));
        if (signal?.aborted) abort();
        else signal?.addEventListener('abort', abort, { once: true });
    })) as typeof fetch;

// Every RTK Query API slice of the app's store, empty again after each test: no cached result, running query,
// polling timer or cache-removal timer of one test reaches the next one, or outlives its file. The slices come
// from the one list the store is built from (store/api-slices.ts), so a new slice is covered without editing
// this file. A test with its own store resets that one itself. A request still in flight when its test ends
// (also one a test stubs `fetch` for) is dropped with it, so its answer cannot reach the store later.
// Only a file that loaded the store is touched: importing the store into the files that never use it would
// add about a fifth to the run. If Vitest's module list is not readable, the store is imported regardless.
let storeLoaded = false;
async function resetApiSlices() {
    try {
        if (!storeLoaded) {
            const loaded = (globalThis as any).__vitest_worker__?.evaluatedModules?.idToModuleMap;
            if (loaded) {
                for (const id of loaded.keys()) if (id.endsWith('/src/store/store.ts')) storeLoaded = true;
                if (!storeLoaded) return;
            }
        }
        const [{ store }, { API_SLICES }] = await Promise.all([import('@app/store/store'), import('@app/store/api-slices')]);
        if (typeof store?.dispatch !== 'function') return;
        for (const api of API_SLICES) store.dispatch(api.util.resetApiState());
    } catch {
        // a test that replaced the store module with a stand-in has no real slices to empty
    }
}

afterEach(async () => {
    cleanup();
    await resetApiSlices();
});

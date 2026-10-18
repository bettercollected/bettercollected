import { createStore } from 'jotai';
import { describe, expect, it } from 'vitest';

import { dispatchAtom, docHistoryAtom, formDocAtom, resetFromServerAtom, undoAtom } from './form-document';
import { adoptSavedLanguageAtom, formLanguageAtom } from './form-language';

function storeWith(settings?: Record<string, unknown>) {
    const store = createStore();
    store.set(resetFromServerAtom, { formId: 'f1', title: 'Taal', ...(settings ? { settings } : {}), fields: [] } as any);
    return store;
}

describe('adoptSavedLanguageAtom', () => {
    it('change, undo back to an imported tag, save: the builder shows what the server keeps', () => {
        const store = storeWith({ language: 'en-GB', purpose: 'To plan.' });
        store.set(dispatchAtom, { ops: [{ op: 'set_form_language', language: 'nl' }] });
        store.set(undoAtom);
        // the undo restored the document exactly; the server keeps "nl" for "en-GB"
        expect(store.get(formLanguageAtom)).toBe('en-GB');
        const steps = store.get(docHistoryAtom).steps.length;

        expect(store.set(adoptSavedLanguageAtom, { sent: 'en-GB', saved: 'nl' })).toBe(true);
        expect(store.get(formLanguageAtom)).toBe('nl');
        // a remote change: no undo step, other settings kept
        expect(store.get(docHistoryAtom).steps.length).toBe(steps);
        expect(store.get(formDocAtom).settings).toEqual({ language: 'nl', purpose: 'To plan.' });
    });

    it('leaves a language changed since the save', () => {
        const store = storeWith({ language: 'de' });
        store.set(dispatchAtom, { ops: [{ op: 'set_form_language', language: 'fr' }] });
        expect(store.set(adoptSavedLanguageAtom, { sent: 'de', saved: 'nl' })).toBe(false);
        expect(store.get(formLanguageAtom)).toBe('fr');
    });

    it('changes nothing when the server stored what was sent', () => {
        const store = storeWith({ language: 'de' });
        expect(store.set(adoptSavedLanguageAtom, { sent: 'de', saved: 'de' })).toBe(false);
        expect(store.get(formLanguageAtom)).toBe('de');
    });
});

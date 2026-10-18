// The form's declared language comes with the form read, while a settings
// change answers with the workspace's settings for the form, which do not
// hold it. Applying those must not drop the language.
import { describe, expect, it } from 'vitest';

import { setForm, setFormSettings, slice } from './slice';

const reduce = slice.reducer;

describe('setFormSettings', () => {
    const withLanguage = reduce(undefined, setForm({ formId: 'f1', title: 'Taal', settings: { customUrl: 'taal', language: 'nl' } } as any));

    it('keeps the form language when the new settings do not carry one', () => {
        const next = reduce(withLanguage, setFormSettings({ customUrl: 'taal', private: true }));
        expect(next.settings).toEqual({ customUrl: 'taal', private: true, language: 'nl' });
    });

    it('takes a language the new settings do carry', () => {
        expect(reduce(withLanguage, setFormSettings({ customUrl: 'taal', language: 'en' })).settings?.language).toBe('en');
        expect(reduce(withLanguage, setFormSettings({ customUrl: 'taal', language: null })).settings?.language).toBeNull();
    });

    it('adds nothing to a form without a language', () => {
        const plain = reduce(undefined, setForm({ formId: 'f2', title: 'Plain', settings: { customUrl: 'plain' } } as any));
        expect(reduce(plain, setFormSettings({ customUrl: 'plain', private: true })).settings).toEqual({ customUrl: 'plain', private: true });
    });
});

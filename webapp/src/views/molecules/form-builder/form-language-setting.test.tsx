import { act, fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider, createStore } from 'jotai';
import { afterEach, describe, expect, it } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { FORM_LANGUAGES } from '@app/lib/form-ops';
import { docHistoryAtom, resetFromServerAtom, undoAtom } from '@app/store/jotai/form-document';
import { formLanguageAtom } from '@app/store/jotai/form-language';

import FormLanguageSetting from './form-language-setting';

function renderWith(settings?: Record<string, unknown>) {
    const store = createStore();
    store.set(resetFromServerAtom, { formId: 'f1', title: 'Taal', ...(settings ? { settings } : {}), fields: [] } as any);
    render(
        <Provider store={store}>
            <FormLanguageSetting />
        </Provider>
    );
    return store;
}

const select = () => screen.getByRole('combobox', { name: 'Form language' });

afterEach(async () => {
    await act(() => i18n.changeLanguage('en'));
});

describe('FormLanguageSetting', () => {
    it('offers "Not set" and every language under its own name', () => {
        renderWith();
        expect(select()).toHaveValue('');
        expect(select()).toHaveAccessibleDescription('The language the questions are written in. It tells screen readers and browsers which language to read them in.');
        const options = within(select()).getAllByRole('option');
        expect(options.map((o) => o.textContent)).toEqual(['Not set', ...FORM_LANGUAGES.map((l) => l.name)]);
        // each name is marked with its own language
        expect(within(select()).getByRole('option', { name: 'Nederlands' })).toHaveAttribute('lang', 'nl');
        expect(within(select()).getByRole('option', { name: 'Suomi' })).toHaveAttribute('lang', 'fi');
    });

    it('shows the language the form has', () => {
        renderWith({ language: 'de', purpose: 'To plan.' });
        expect(select()).toHaveValue('de');
    });

    it('sets the language through the op, as one undo step', () => {
        const store = renderWith({ purpose: 'To plan.' });
        select().focus();
        expect(select()).toHaveFocus();
        fireEvent.change(select(), { target: { value: 'nl' } });
        expect(store.get(formLanguageAtom)).toBe('nl');
        const step = store.get(docHistoryAtom).steps.at(-1);
        expect(step?.forward).toEqual([{ op: 'set_form_language', language: 'nl' }]);
        expect(select()).toHaveValue('nl');

        act(() => {
            store.set(undoAtom);
        });
        expect(store.get(formLanguageAtom)).toBeNull();
        expect(select()).toHaveValue('');
    });

    it('"Not set" clears it', () => {
        const store = renderWith({ language: 'fr' });
        fireEvent.change(select(), { target: { value: '' } });
        expect(store.get(formLanguageAtom)).toBeNull();
        expect(store.get(docHistoryAtom).steps.at(-1)?.forward).toEqual([{ op: 'set_form_language', language: null }]);
    });

    it('keeps a language set elsewhere that is not on the list', () => {
        renderWith({ language: 'en-GB' });
        expect(select()).toHaveValue('en-GB');
        expect(within(select()).getByRole('option', { name: 'en-GB' })).toHaveAttribute('lang', 'en-GB');
    });

    it('gives a malformed tag set elsewhere no lang', () => {
        renderWith({ language: 'not a tag' });
        expect(within(select()).getByRole('option', { name: 'not a tag' })).not.toHaveAttribute('lang');
    });

    it('undo puts back a language set elsewhere exactly', () => {
        // the op refuses "en-GB", so undo restores the document as it was
        // (the server keeps the language it has for such a tag)
        const store = renderWith({ language: 'en-GB' });
        fireEvent.change(select(), { target: { value: 'nl' } });
        expect(store.get(formLanguageAtom)).toBe('nl');
        act(() => {
            store.set(undoAtom);
        });
        expect(store.get(formLanguageAtom)).toBe('en-GB');
        expect(select()).toHaveValue('en-GB');
    });

    it('reads in Dutch', async () => {
        await act(() => i18n.changeLanguage('nl'));
        renderWith();
        const field = screen.getByRole('combobox', { name: 'Taal van het formulier' });
        expect(within(field).getByRole('option', { name: 'Niet ingesteld' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Taal' })).toBeInTheDocument();
    });
});

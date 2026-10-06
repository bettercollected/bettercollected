import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18next';
import { Provider } from 'jotai';
import { beforeEach, describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { RichTextEditor } from '@app/views/molecules/rich-text-editor';

import enBuilder from '../../../../public/locales/en/builder.json';
import nlBuilder from '../../../../public/locales/nl/builder.json';
import PlainLanguageHints from './plain-language-hints';

const doc = (text: string) => ({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] });

const form = (title: object): StandardFormFieldDto[] => [
    {
        id: 's1',
        index: 0,
        type: FieldTypes.SLIDE,
        properties: { fields: [{ id: 'q1', index: 0, type: FieldTypes.SHORT_TEXT, title: title as any }] }
    }
];

let api: ReturnType<typeof useFormFieldsAtom> | null = null;

/** The builder's title row as slide-builder renders it: editor, then tips. */
function TitleWithHints({ title }: { title: object }) {
    const fields = useFormFieldsAtom();
    api = fields;
    const [ready, setReady] = React.useState(false);
    React.useEffect(() => {
        fields.initFormFields(form(title));
        setReady(true);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    const slide = fields.formFields[0];
    const field = slide?.properties?.fields?.[0];
    if (!ready || !slide || !field) return null;
    return (
        <div>
            <RichTextEditor field={field} slide={slide} describedById="plain-language-title-q1" />
            <PlainLanguageHints id="plain-language-title-q1" value={field.title} formId="form-1" debounceMs={10} />
        </div>
    );
}

const renderTitle = (text: string) =>
    render(
        <Provider>
            <TitleWithHints title={doc(text)} />
        </Provider>
    );

const tipsList = () => screen.queryByRole('list', { name: 'Plain-language tips' });

beforeEach(() => {
    window.localStorage.clear();
    api = null;
});

describe('PlainLanguageHints in the builder', () => {
    it('shows a tip under the title, linked to the title by aria-describedby', async () => {
        renderTitle('Indien u vragen heeft, belt u ons.');
        await waitFor(() => expect(tipsList()).toBeInTheDocument());
        expect(tipsList()).toHaveTextContent('“Indien” is officialese. Plainer: “als”.');

        const titleInput = await waitFor(() => {
            const element = document.querySelector('[contenteditable="true"]');
            expect(element).not.toBeNull();
            return element as HTMLElement;
        });
        expect(titleInput).toHaveAttribute('aria-describedby', 'plain-language-title-q1');
        expect(document.getElementById('plain-language-title-q1')).toHaveTextContent('“Indien” is officialese');
        // Advisory only: the title is never marked invalid.
        expect(titleInput).not.toHaveAttribute('aria-invalid');
    });

    it('never blocks saving: title edits reach the form state while tips show', async () => {
        renderTitle('Indien u vragen heeft, belt u ons.');
        await waitFor(() => expect(tipsList()).toBeInTheDocument());

        // What the editor does on every change; AutoSaveForm saves this state.
        act(() => api!.updateTitle(0, 0, doc('Your receipt will be sent by email in order to confirm it.') as any));
        expect(api!.formFields[0].properties!.fields![0].title).toEqual(doc('Your receipt will be sent by email in order to confirm it.'));

        await waitFor(() => expect(tipsList()).toHaveTextContent('“in order to” is officialese. Plainer: “to”.'));
        expect(tipsList()).toHaveTextContent('“be sent” is passive.');
        // No tip disables anything; the only controls are the dismiss buttons.
        expect(screen.getAllByRole('button', { name: 'Dismiss tip' })).toHaveLength(2);
        expect(document.querySelectorAll('[disabled]')).toHaveLength(0);
    });

    it('announces changes politely, not on mount', async () => {
        renderTitle('Wat is uw naam?');
        const live = document.querySelector('[aria-live="polite"]')!;
        expect(live).toHaveTextContent('');
        expect(tipsList()).toBeNull();

        await waitFor(() => expect(api).not.toBeNull());
        act(() => api!.updateTitle(0, 0, doc('Wat is uw naam en/of adres?') as any));
        await waitFor(() => expect(live).toHaveTextContent('1 plain-language tip for this text'));
        expect(tipsList()).toHaveTextContent('“en/of” asks two things at once.');
    });

    it('lets the creator dismiss a tip for this field, and remembers it', async () => {
        const { unmount } = renderTitle('Indien u vragen heeft, belt u ons.');
        await waitFor(() => expect(tipsList()).toBeInTheDocument());
        fireEvent.click(screen.getByRole('button', { name: 'Dismiss tip' }));
        expect(tipsList()).toBeNull();
        unmount();

        renderTitle('Indien u vragen heeft, belt u ons.');
        await waitFor(() => expect(document.querySelector('[contenteditable="true"]')).not.toBeNull());
        expect(tipsList()).toBeNull();
    });
});

describe('plain-language strings', () => {
    it('exist in English and Dutch', () => {
        expect(Object.keys(nlBuilder.PLAIN_LANGUAGE).sort()).toEqual(Object.keys(enBuilder.PLAIN_LANGUAGE).sort());
        const tNl = i18n.getFixedT('nl', 'builder');
        expect(tNl('PLAIN_LANGUAGE.JARGON', { match: 'middels', suggestion: 'met, via' })).toBe('“middels” is ambtelijk. Eenvoudiger: “met, via”.');
        expect(tNl('PLAIN_LANGUAGE.ANNOUNCE', { count: 2 })).toBe('2 tips voor duidelijke taal bij deze tekst');
    });
});

// A question title points at its plain-language tips (aria-describedby) only
// while the tips are rendered: on the question being edited. Other titles
// never reference an id that isn't in the page.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { activeFieldAtom, activeSlideAtom } from '@app/store/jotai/active-builder-component';
import { resetFromServerAtom } from '@app/store/jotai/form-document';
import { store as reduxStore } from '@app/store/store';

import SlideBuilder from './slide-builder';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/dashboard/forms/f1/edit',
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    useSearchParams: () => new URLSearchParams()
}));
// The editor stands in as a textbox carrying the description it is given.
vi.mock('@app/views/molecules/rich-text-editor', () => ({
    RichTextEditor: ({ field, describedById }: { field: StandardFormFieldDto; describedById?: string }) => <div role="textbox" aria-label={`title ${field.id}`} aria-describedby={describedById} />
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ default: () => null }));
vi.mock('@app/views/molecules/form-builder/plain-language-hints', () => ({ default: ({ id }: { id: string }) => <div id={id} /> }));
vi.mock('@app/lib/hooks/use-form-logo', () => ({ useBuilderFormLogo: () => null }));

const form = () => ({
    formId: 'form-1',
    title: 'Form',
    fields: [
        {
            id: 'page-1',
            index: 0,
            type: FieldTypes.SLIDE,
            properties: {
                fields: [
                    { id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name' },
                    { id: 'q-2', index: 1, type: FieldTypes.SHORT_TEXT, title: 'City' }
                ]
            }
        }
    ]
});

describe('plain-language tips and the title they describe', () => {
    it('only the edited question’s title points at its tips, and the tips exist', () => {
        const jotai = createStore();
        jotai.set(resetFromServerAtom, form() as any);
        jotai.set(activeSlideAtom, { id: 'page-1', index: 0 });
        jotai.set(activeFieldAtom, { id: 'q-2', index: 1 });
        render(
            <ReduxProvider store={reduxStore}>
                <Provider store={jotai}>
                    <SlideBuilder pageId="page-1" />
                </Provider>
            </ReduxProvider>
        );
        const edited = screen.getByRole('textbox', { name: 'title q-2' });
        expect(edited).toHaveAttribute('aria-describedby', 'plain-language-title-q-2');
        expect(document.getElementById('plain-language-title-q-2')).not.toBeNull();

        expect(screen.getByRole('textbox', { name: 'title q-1' })).not.toHaveAttribute('aria-describedby');
        expect(document.getElementById('plain-language-title-q-1')).toBeNull();
    });
});

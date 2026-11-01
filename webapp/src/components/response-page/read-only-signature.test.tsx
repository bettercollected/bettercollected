import React from 'react';

import { render, screen, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import ReadOnlyForm from './read-only-form';

const form = (language?: string) =>
    ({
        formId: 'f',
        title: 'Agreement',
        builderVersion: 'v2',
        version: 1,
        settings: { provider: 'self', ...(language ? { language } : {}) },
        fields: [
            {
                id: 'p1',
                index: 0,
                type: FieldTypes.SLIDE,
                properties: {
                    fields: [
                        { id: 'typed', index: 0, type: FieldTypes.SIGNATURE, title: 'Sign for yourself', properties: {} },
                        { id: 'drawn', index: 1, type: FieldTypes.SIGNATURE, title: 'Sign for your partner', properties: {} },
                        { id: 'none', index: 2, type: FieldTypes.SIGNATURE, title: 'Sign for the witness', properties: {} }
                    ]
                }
            }
        ]
    }) as any;

const response = (answers: Record<string, any>) => ({ responseId: 'r', createdAt: '2026-10-01T10:00:00Z', answers }) as any;
const ANSWERS = {
    typed: { field: { id: 'typed' }, type: 'signature', signature: { method: 'typed', name: 'Fatima El Idrissi', signed_at: '2026-11-01T09:31:12Z' } },
    drawn: { field: { id: 'drawn' }, type: 'signature', signature: { method: 'drawn', file_id: 'img-1', signed_at: '2026-11-01T09:30:00Z', url: 'https://files.example/private/ws/f/r/img-1?signed' } }
};

const show = (language?: string, answers: Record<string, any> = ANSWERS) =>
    render(
        <ReduxProvider store={store}>
            <ReadOnlyForm form={form(language)} response={response(answers)} />
        </ReduxProvider>
    );

beforeEach(() => {
    store.dispatch(setWorkspace({ id: 'workspace-1', workspaceName: 'acme' } as any));
});

describe('a signature on the response page', () => {
    it('shows a typed name as text (the name is the signature) and when it was signed', () => {
        show();
        const group = screen.getAllByRole('group', { name: /Sign for yourself/ })[0];
        expect(within(group).getByText('Fatima El Idrissi')).toBeInTheDocument();
        expect(within(group).getByText(/Signed 1 November 2026/)).toBeInTheDocument();
        expect(group.querySelector('img')).toBeNull();
    });

    it('shows a drawn signature as its image, with a text alternative', () => {
        show();
        const group = screen.getAllByRole('group', { name: /Sign for your partner/ })[0];
        const image = within(group).getByRole('img', { name: 'Drawn signature' });
        expect(image).toHaveAttribute('src', 'https://files.example/private/ws/f/r/img-1?signed');
    });

    it('says so when a drawn signature has no link (the file is gone)', () => {
        show(undefined, { drawn: { type: 'signature', signature: { method: 'drawn', file_id: 'img-1' } } });
        expect(screen.getByText(/Drawn signature \(the image is not available\)/)).toBeInTheDocument();
    });

    it('says there is no answer for a question left unsigned', () => {
        show();
        const group = screen.getAllByRole('group', { name: /Sign for the witness/ })[0];
        expect(within(group).getByText(/No answer/i)).toBeInTheDocument();
    });

    it('writes the time in the form’s language', () => {
        show('nl');
        expect(screen.getAllByText(/Signed 1 november 2026/).length).toBeGreaterThan(0);
    });

    it('has no accessibility violations', async () => {
        const { container } = show();
        expect(await axeViolations(container)).toEqual([]);
    });
});

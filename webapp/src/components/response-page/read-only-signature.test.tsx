import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
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
    drawn: { field: { id: 'drawn' }, type: 'signature', signature: { method: 'drawn', file_id: 'img-1', signed_at: '2026-11-01T09:30:00Z', url: '/workspaces/workspace-1/submissions/r/signatures/drawn' } }
};

const show = (language?: string, answers: Record<string, any> = ANSWERS) =>
    render(
        <ReduxProvider store={store}>
            <ReadOnlyForm form={form(language)} response={response(answers)} />
        </ReduxProvider>
    );

const PNG_RESPONSE = () => new Response(new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: 'image/png' }), { status: 200, headers: { 'content-type': 'image/png' } });

beforeEach(() => {
    store.dispatch(setWorkspace({ id: 'workspace-1', workspaceName: 'acme' } as any));
    // the image comes from the API (decrypted there), fetched with the user's credentials
    vi.stubGlobal(
        'fetch',
        vi.fn(async () => PNG_RESPONSE())
    );
    URL.createObjectURL = vi.fn(() => 'blob:signature-1');
    URL.revokeObjectURL = vi.fn();
});

afterEach(async () => {
    vi.unstubAllGlobals();
    await act(() => i18n.changeLanguage('en'));
});

describe('a signature on the response page', () => {
    it('shows a typed name as text (the name is the signature) and when it was signed', () => {
        show();
        const group = screen.getAllByRole('group', { name: /Sign for yourself/ })[0];
        expect(within(group).getByText('Fatima El Idrissi')).toBeInTheDocument();
        // the full time with its zone, like "Submitted"
        expect(within(group).getByText(/^Signed 1 November 2026(,| at) \d\d:\d\d:\d\d \S+$/)).toBeInTheDocument();
        expect(group.querySelector('img')).toBeNull();
    });

    it('shows a drawn signature as its image, with a text alternative', async () => {
        show();
        const group = screen.getAllByRole('group', { name: /Sign for your partner/ })[0];
        const image = await within(group).findByRole('img', { name: 'Drawn signature' });
        // fetched from the API with the user's credentials, shown from a blob address
        expect(image).toHaveAttribute('src', 'blob:signature-1');
        expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/workspaces\/workspace-1\/submissions\/r\/signatures\/drawn$/), expect.objectContaining({ credentials: 'include' }));
        expect(image).toHaveAttribute('referrerpolicy', 'no-referrer');
    });

    it('says the image is not available when it does not load', async () => {
        show();
        const group = screen.getAllByRole('group', { name: /Sign for your partner/ })[0];
        fireEvent.error(await within(group).findByRole('img', { name: 'Drawn signature' }));
        expect(within(group).queryByRole('img')).toBeNull();
        expect(within(group).getByText('Drawn signature (the image is not available)')).toBeInTheDocument();
    });

    it('says so when the server refuses the image', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => new Response('Not Found', { status: 404 }))
        );
        show();
        const group = screen.getAllByRole('group', { name: /Sign for your partner/ })[0];
        expect(await within(group).findByText('Drawn signature (the image is not available)')).toBeInTheDocument();
        expect(within(group).queryByRole('img')).toBeNull();
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

    it('writes the label and the time in one language', async () => {
        show('nl');
        // the page's language, whatever the form's: never "Signed 1 november"
        expect(screen.queryByText(/Signed 1 november/)).toBeNull();
        expect(screen.getAllByText(/^Signed 1 November 2026/).length).toBeGreaterThan(0);
        await act(() => i18n.changeLanguage('nl'));
        expect(screen.getAllByText(/^Ondertekend op 1 november 2026/).length).toBeGreaterThan(0);
        expect(await screen.findByRole('img', { name: 'Getekende handtekening' })).toBeInTheDocument();
    });

    it('has no accessibility violations', async () => {
        const { container } = show();
        await screen.findByRole('img', { name: 'Drawn signature' });
        expect(await axeViolations(container)).toEqual([]);
    });
});

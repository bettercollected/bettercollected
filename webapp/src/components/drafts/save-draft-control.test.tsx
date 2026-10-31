// "Save and continue later" on a question page: signed in it saves to the
// account, otherwise the respondent enters an address once and gets a link.
// What is sent, what is said, and that it is accessible, in English and Dutch.
import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeColors } from '@app/constants/theme';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setAuth } from '@app/store/auth/slice';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';
import FormSlide from '@app/views/organism/form/form-slide';

const save = vi.fn();
const requestLink = vi.fn();
const discard = vi.fn();
const submit = vi.fn();
vi.mock('@app/store/redux/drafts-api', async (original) => ({
    ...((await original()) as object),
    useSaveDraftMutation: () => [save, { isLoading: false }],
    useRequestDraftLinkMutation: () => [requestLink, { isLoading: false }],
    useDiscardDraftMutation: () => [discard, { isLoading: false }]
}));
vi.mock('@app/store/redux/form-api', async (original) => ({
    ...((await original()) as object),
    useSubmitResponseMutation: () => [submit, { isLoading: false }]
}));
vi.mock('next/navigation', () => ({ usePathname: () => '/acme/forms/f1', useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));

const q = (id: string, title: string, type = FieldTypes.SHORT_TEXT): StandardFormFieldDto => ({ id, index: 0, type, title, properties: { fields: [] }, validations: { required: false } });
const page = (id: string, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SLIDE, title: '', properties: { fields } });

let response: ReturnType<typeof useFormResponse> | null = null;

function Respondent({ preview = false }: { preview?: boolean }) {
    const responder = useResponderState();
    response = useFormResponse();
    const { updateFormTheme } = useFormState();
    React.useEffect(() => {
        updateFormTheme(ThemeColors[0], { undoable: false });
        responder.setResponderState({ ...responder.responderState, currentSlide: 0, history: [-1] });
    }, []);
    return <FormSlide index={0} isPreviewMode={preview} />;
}

const open = (settings: Record<string, unknown> = { allowSaveDraft: true }, { preview = false, fields = [q('a', 'Your name'), q('cv', 'Upload your CV', FieldTypes.FILE_UPLOAD)] }: { preview?: boolean; fields?: StandardFormFieldDto[] } = {}) => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    store.dispatch(setForm({ formId: `f-${Math.random()}`, builderVersion: 'v2', version: 3, title: 'Survey', settings, fields: [page('s1', fields)] } as any));
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Respondent preview={preview} />
            </Provider>
        </ReduxProvider>
    );
};

const type = async (id: string, value: string) => {
    act(() => void fireEvent.change(document.getElementById(`input-field-${id}`)!, { target: { value } }));
    await act(() => new Promise((resolve) => setTimeout(resolve, 350)));
};
const click = (name: string | RegExp) => act(async () => void fireEvent.click(screen.getByRole('button', { name })));

const COPY = {
    en: { save: 'Save and continue later', label: 'Your email address', send: 'Send me the link', changes: 'Save changes', remove: 'Delete my draft', again: 'Send the link again', cancel: 'Cancel' },
    nl: { save: 'Opslaan en later verder', label: 'Je e-mailadres', send: 'Stuur me de link', changes: 'Wijzigingen opslaan', remove: 'Mijn concept verwijderen', again: 'Stuur de link opnieuw', cancel: 'Annuleren' }
} as const;

describe('save and continue later', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
        for (const mock of [save, requestLink, discard, submit]) mock.mockReset();
        save.mockResolvedValue({ data: { savedAt: '2026-11-01T10:00:00Z', expiresAt: '2026-12-01T10:00:00Z' } });
        requestLink.mockResolvedValue({ data: { savedAt: '2026-11-01T10:00:00Z', expiresAt: '2026-12-01T10:00:00Z', editKey: `${'a'.repeat(24)}.${'K'.repeat(43)}` } });
        discard.mockResolvedValue({ data: { deleted: true } });
        submit.mockResolvedValue({ data: 'receipt-1' });
    });
    afterEach(() => {
        window.history.replaceState(null, '', '/');
        store.dispatch(setAuth({ id: '', email: '' }));
    });

    it('is not offered when the form does not keep drafts, in the builder preview, or when a verified identity is needed first', async () => {
        const { unmount } = open({});
        await screen.findByRole('textbox', { name: 'Your name' });
        expect(screen.queryByRole('button', { name: COPY.en.save })).toBeNull();
        unmount();
        const preview = open({ allowSaveDraft: true }, { preview: true });
        await screen.findByRole('textbox', { name: 'Your name' });
        expect(screen.queryByRole('button', { name: COPY.en.save })).toBeNull();
        preview.unmount();
        open({ allowSaveDraft: true, requireVerifiedIdentity: true });
        await screen.findByRole('textbox', { name: 'Your name' });
        expect(screen.queryByRole('button', { name: COPY.en.save })).toBeNull();
        // signed in, the same form offers it
        store.dispatch(setAuth({ id: 'user-1', email: 'ada@example.com' }));
        open({ allowSaveDraft: true, requireVerifiedIdentity: true });
        expect(await screen.findAllByRole('button', { name: COPY.en.save })).not.toHaveLength(0);
    });

    it.each(['en', 'nl'] as const)('asks an anonymous respondent for an address, sends it with the answers and the place, and says where the link went (%s)', async (lang) => {
        window.history.replaceState(null, '', `/acme/forms/f1?lang=${lang}`);
        const c = COPY[lang];
        open();
        await type('a', 'Ada');
        await click(c.save);
        const email = screen.getByLabelText(c.label) as HTMLInputElement;
        expect(email).toHaveFocus();
        expect(email.type).toBe('email');
        expect(email.getAttribute('autocomplete')).toBe('email');
        expect(email.getAttribute('aria-describedby')).toBeTruthy();
        // nothing leaves until they ask
        expect(requestLink).not.toHaveBeenCalled();
        expect((screen.getByRole('button', { name: c.send }) as HTMLButtonElement).disabled).toBe(true);
        fireEvent.change(email, { target: { value: ' ada@example.com ' } });
        await click(c.send);

        expect(requestLink).toHaveBeenCalledTimes(1);
        const call = requestLink.mock.calls[0][0];
        expect(call.workspaceId).toBe('ws-1');
        expect(call.body).toMatchObject({ email: 'ada@example.com', locale: lang, formVersion: 3, position: { pageId: 's1', history: [] } });
        expect(call.body.answers).toEqual({ a: { type: 'text', text: 'Ada' } });
        expect(call.body.editKey).toBeUndefined();
        const message = await screen.findByText(/ada@example\.com/);
        expect(message.textContent).toContain(lang === 'en' ? 'We sent a link to ada@example.com. It works for 7 days.' : 'We hebben een link gestuurd naar ada@example.com. De link werkt 7 dagen.');
        // focus moved to the confirmation (the form that held it is gone)
        await waitFor(() => expect(message).toHaveFocus());
        expect(screen.getByRole('button', { name: c.changes })).toBeTruthy();
        expect(screen.getByRole('button', { name: c.again })).toBeTruthy();
        expect(screen.getByRole('button', { name: c.remove })).toBeTruthy();
    });

    it('keeps files out and says so', async () => {
        open();
        await screen.findByRole('textbox', { name: 'Your name' });
        await click(COPY.en.save);
        expect(screen.getByText('Files you added are not saved. You add them again when you continue.')).toBeTruthy();
    });

    it('saves changes with the edit key, without another mail, and deletes on request', async () => {
        open();
        await type('a', 'Ada');
        await click(COPY.en.save);
        fireEvent.change(screen.getByLabelText(COPY.en.label), { target: { value: 'ada@example.com' } });
        await click(COPY.en.send);
        await screen.findByText(/We sent a link/);

        await type('a', 'Ada L.');
        await click(COPY.en.changes);
        expect(requestLink).toHaveBeenCalledTimes(1);
        expect(save).toHaveBeenCalledTimes(1);
        expect(save.mock.calls[0][0].body.editKey).toBe(`${'a'.repeat(24)}.${'K'.repeat(43)}`);
        expect(save.mock.calls[0][0].body.answers).toEqual({ a: { type: 'text', text: 'Ada L.' } });
        expect(await screen.findByText(/Changes saved\. Your draft is kept until 1 December 2026\./)).toBeTruthy();

        await click(COPY.en.remove);
        expect(discard).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: expect.any(String), editKey: `${'a'.repeat(24)}.${'K'.repeat(43)}` });
        expect(await screen.findByText('Your draft was deleted.')).toBeTruthy();
        // and the next save starts over with an address
        expect(screen.getByRole('button', { name: COPY.en.save })).toBeTruthy();
    });

    it('sends the link again to another address with the same draft', async () => {
        open();
        await click(COPY.en.save);
        fireEvent.change(screen.getByLabelText(COPY.en.label), { target: { value: 'ada@example.com' } });
        await click(COPY.en.send);
        await screen.findByText(/We sent a link/);
        await click(COPY.en.again);
        fireEvent.change(screen.getByLabelText(COPY.en.label), { target: { value: 'ada@work.example' } });
        await click(COPY.en.send);
        expect(requestLink).toHaveBeenCalledTimes(2);
        expect(requestLink.mock.calls[1][0].body).toMatchObject({ email: 'ada@work.example', editKey: `${'a'.repeat(24)}.${'K'.repeat(43)}` });
    });

    it('cancelling closes the address form and gives focus back', async () => {
        open();
        await click(COPY.en.save);
        await click(COPY.en.cancel);
        expect(screen.queryByLabelText(COPY.en.label)).toBeNull();
        await waitFor(() => expect(screen.getByRole('button', { name: COPY.en.save })).toHaveFocus());
        expect(requestLink).not.toHaveBeenCalled();
    });

    it('saves to the account when signed in, without asking for an address', async () => {
        store.dispatch(setAuth({ id: 'user-1', email: 'ada@example.com' }));
        open();
        await type('a', 'Ada');
        await click(COPY.en.save);
        expect(screen.queryByLabelText(COPY.en.label)).toBeNull();
        expect(requestLink).not.toHaveBeenCalled();
        expect(save).toHaveBeenCalledTimes(1);
        expect(save.mock.calls[0][0].body.editKey).toBeUndefined();
        expect(await screen.findByText('Saved to your account. It is kept until 1 December 2026. Sign in and open this form again to continue.')).toBeTruthy();
    });

    it.each([
        [{ status: 429, data: { code: 'rate_limited' } }, 'Too many attempts. Wait a few minutes and try again.'],
        [{ status: 409, data: { code: 'form_closed' } }, 'This form no longer takes responses, so a draft cannot be saved.'],
        [{ status: 404, data: { code: 'drafts_off' } }, 'This form no longer keeps drafts.'],
        [{ status: 413, data: { code: 'draft_too_large' } }, 'Your draft is too large to save.'],
        [{ status: 503, data: { code: 'link_not_sent' } }, 'We could not send the link. Try again in a moment.'],
        [{ status: 422, data: { code: 'invalid_email' } }, 'Enter a valid email address.'],
        [{ status: 500 }, 'Your draft could not be saved. Try again.']
    ])('says what went wrong: %j', async (error, message) => {
        requestLink.mockResolvedValue({ error });
        open();
        await click(COPY.en.save);
        fireEvent.change(screen.getByLabelText(COPY.en.label), { target: { value: 'ada@example.com' } });
        await click(COPY.en.send);
        expect((await screen.findByRole('alert')).textContent).toBe(message);
        // the address form stays, with what they typed, to try again
        expect((screen.getByLabelText(COPY.en.label) as HTMLInputElement).value).toBe('ada@example.com');
    });

    it('starts over with an address when the key no longer opens a draft', async () => {
        open();
        await click(COPY.en.save);
        fireEvent.change(screen.getByLabelText(COPY.en.label), { target: { value: 'ada@example.com' } });
        await click(COPY.en.send);
        await screen.findByText(/We sent a link/);
        save.mockResolvedValue({ error: { status: 404, data: { code: 'draft_not_found' } } });
        await click(COPY.en.changes);
        expect((await screen.findByRole('alert')).textContent).toBe('We could not find your draft. Send yourself a new link.');
        expect(screen.getByRole('button', { name: COPY.en.save })).toBeTruthy();
    });

    it('sends the edit key with the submission, so the server deletes the draft', async () => {
        open({ allowSaveDraft: true }, { fields: [q('a', 'Your name')] });
        await type('a', 'Ada');
        await click(COPY.en.save);
        fireEvent.change(screen.getByLabelText(COPY.en.label), { target: { value: 'ada@example.com' } });
        await click(COPY.en.send);
        await screen.findByText(/We sent a link/);
        await click('Submit response');
        expect(submit).toHaveBeenCalledTimes(1);
        const body = submit.mock.calls[0][0].body as FormData;
        expect(body.get('draft_key')).toBe(`${'a'.repeat(24)}.${'K'.repeat(43)}`);
    });

    it("does not carry one form's draft into another form (no key, no note, nothing sent)", async () => {
        open({ allowSaveDraft: true }, { fields: [q('a', 'Your name')] });
        await type('a', 'Ada');
        await click(COPY.en.save);
        fireEvent.change(screen.getByLabelText(COPY.en.label), { target: { value: 'ada@example.com' } });
        await click(COPY.en.send);
        await screen.findByText(/We sent a link/);
        // the respondent moves on to another form without a reload
        act(() => void store.dispatch(setForm({ formId: 'another-form', builderVersion: 'v2', version: 1, title: 'Other', settings: { allowSaveDraft: true }, fields: [page('s1', [q('a', 'Your name')])] } as any)));
        await screen.findByRole('button', { name: COPY.en.save });
        expect(screen.queryByText(/We sent a link/)).toBeNull();
        expect(screen.queryByRole('button', { name: COPY.en.changes })).toBeNull();
        await click('Submit response');
        expect((submit.mock.calls[0][0].body as FormData).has('draft_key')).toBe(false);
    });

    it('sends no draft key with a submission that has no draft', async () => {
        open({ allowSaveDraft: true }, { fields: [q('a', 'Your name')] });
        await type('a', 'Ada');
        await click('Submit response');
        expect((submit.mock.calls[0][0].body as FormData).has('draft_key')).toBe(false);
        expect(response!.formResponse.answers.a).toBeTruthy();
    });
});

describe.each(['en', 'nl'] as const)('save and continue later passes axe (%s)', (lang) => {
    const c = COPY[lang];
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        window.history.replaceState(null, '', `/acme/forms/f1?lang=${lang}`);
        requestLink.mockResolvedValue({ data: { savedAt: '2026-11-01T10:00:00Z', expiresAt: '2026-12-01T10:00:00Z', editKey: `${'a'.repeat(24)}.${'K'.repeat(43)}` } });
    });
    afterEach(() => {
        window.history.replaceState(null, '', '/');
        store.dispatch(setAuth({ id: '', email: '' }));
    });

    it('the control, the address form, the error and the confirmation', async () => {
        open();
        await screen.findByRole('button', { name: c.save });
        expect(await axeViolations(document, { page: false })).toEqual([]);
        await click(c.save);
        expect(await axeViolations(document, { page: false })).toEqual([]);
        requestLink.mockResolvedValueOnce({ error: { status: 429 } });
        fireEvent.change(screen.getByLabelText(c.label), { target: { value: 'ada@example.com' } });
        await click(c.send);
        await screen.findByRole('alert');
        expect(await axeViolations(document, { page: false })).toEqual([]);
        await click(c.send);
        await screen.findByRole('button', { name: c.changes });
        expect(await axeViolations(document, { page: false })).toEqual([]);
    });
});

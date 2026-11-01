// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import axe from 'axe-core';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import useFormAtom from '@app/store/jotai/form-file';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { store } from '@app/store/store';
import { checkAnswerRules } from '@app/utils/answer-rules';

import SignatureField from './signature-field';

vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const sign: StandardFormFieldDto = { id: 'sig', index: 0, type: FieldTypes.SIGNATURE, title: 'Sign the agreement', description: 'By signing you agree to the terms', validations: { required: true }, properties: {} };

let latest: Record<string, any> = {};
let held: Array<{ fieldId: string; fileId: string; fileName: string; file: File }> = [];
let flag: (codes: Record<string, string[]>) => void = () => undefined;
let flagged: Record<string, unknown> = {};

function Spy() {
    const { formResponse, setFormResponse } = useFormResponse();
    const { files } = useFormAtom();
    latest = formResponse.answers ?? {};
    held = files;
    flagged = formResponse.invalidFields ?? {};
    // what Continue does: the page flags the question
    flag = (codes) => setFormResponse({ ...formResponse, invalidFields: codes });
    return null;
}

const HELD_FILE = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], 'signature.png', { type: 'image/png' });

const show = (answers: Record<string, any> = {}, field: StandardFormFieldDto = sign, isBuilder = false, heldFiles: Array<{ fieldId: string; fileId: string }> = []) => {
    store.dispatch(setForm({ formId: 'f', title: 'Agreement', fields: [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [field] } }] }));
    const Harness = () => {
        const { setFormResponse, formResponse } = useFormResponse();
        const { addFile } = useFormAtom();
        const [ready, setReady] = React.useState(false);
        React.useEffect(() => {
            setFormResponse({ ...formResponse, answers });
            heldFiles.forEach((item) => addFile(item.fieldId, item.fileId, 'signature.png', HELD_FILE));
            setReady(true);
        }, []);
        return ready ? <SignatureField field={field} isBuilder={isBuilder} /> : null;
    };
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Harness />
                <Spy />
            </Provider>
        </ReduxProvider>
    );
};

// jsdom has no canvas: a recording context and a PNG blob stand in.
const painted: string[] = [];
beforeEach(() => {
    painted.length = 0;
    const context = new Proxy(
        {},
        {
            get: (_t, key) => (typeof key === 'string' ? (..._args: unknown[]) => void painted.push(key) : undefined),
            set: () => true
        }
    );
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation((() => context) as any);
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(((cb: BlobCallback) => cb(new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: 'image/png' }))) as any);
    vi.spyOn(HTMLCanvasElement.prototype, 'getBoundingClientRect').mockImplementation(() => ({ left: 0, top: 0, width: 300, height: 100, right: 300, bottom: 100, x: 0, y: 0, toJSON: () => ({}) }));
    (URL as any).createObjectURL = vi.fn(() => 'blob:preview');
    (URL as any).revokeObjectURL = vi.fn();
});

afterEach(() => {
    latest = {};
    held = [];
    vi.restoreAllMocks();
});

/** A pointer event as jsdom can make one (it has no PointerEvent): a mouse event with the pointer's id. */
const pointer = (target: Element, type: string, x: number, y: number, { pointerId = 1, button = 0 }: { pointerId?: number; button?: number } = {}) => {
    const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y, button });
    Object.defineProperty(event, 'pointerId', { value: pointerId });
    return fireEvent(target, event);
};
const drawLine = async (canvas: Element) => {
    await act(async () => {
        pointer(canvas, 'pointerdown', 10, 10);
        pointer(canvas, 'pointermove', 60, 40);
        pointer(canvas, 'pointermove', 120, 20);
        pointer(canvas, 'pointerup', 120, 20);
    });
};

describe('SignatureField', () => {
    it('offers two ways to sign as radio buttons that come before the drawing box, and starts on drawing', async () => {
        show();
        const group = await screen.findByRole('radiogroup', { name: 'Sign the agreement' });
        const radios = within(group).getAllByRole('radio');
        expect(radios.map((radio) => (radio as HTMLInputElement).labels?.[0]?.textContent)).toEqual(['Draw', 'Type your name']);
        expect(radios[0]).toBeChecked();
        // a native radio group: Tab reaches it, the arrow keys move inside it
        expect(radios[0].tagName).toBe('INPUT');
        // the radios precede the canvas in the document (and so in the tab order)
        const canvas = screen.getByRole('img', { name: 'Signature drawing area' });
        expect(radios[1].compareDocumentPosition(canvas) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });

    it('names the drawing box and describes it, including the way out for those who cannot draw', async () => {
        show();
        const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
        expect(canvas).toHaveAccessibleDescription(/Draw your signature in the box.*Type your name/s);
        // the box never traps keyboard focus: a canvas is not focusable, and nothing here sets a tab stop
        expect(canvas).not.toHaveAttribute('tabindex');
        expect(canvas).toHaveStyle({ touchAction: 'none' });
    });

    it('draws: a stroke makes a PNG file part and the answer holds its id', async () => {
        show();
        const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
        await drawLine(canvas);
        expect(latest.sig.type).toBe('signature');
        expect(latest.sig.signature.method).toBe('drawn');
        expect(latest.sig.signature.file_id).toMatch(/^[0-9a-f-]{36}$/);
        expect(held).toHaveLength(1);
        expect(held[0].fieldId).toBe('sig');
        expect(held[0].fileId).toBe(latest.sig.signature.file_id);
        expect(held[0].file.type).toBe('image/png');
        expect(held[0].fileName).toBe('signature.png');
        expect(painted).toContain('stroke');
        expect(checkAnswerRules(sign, latest.sig)).toEqual([]);
        // nothing but the id is in the answer: no image, no time (the server stamps it)
        expect(Object.keys(latest.sig.signature).sort()).toEqual(['file_id', 'method']);
    });

    it('announces added and cleared, and Clear removes the drawing and the answer', async () => {
        show();
        const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
        const clear = screen.getByRole('button', { name: 'Clear signature' });
        expect(clear).toBeDisabled();
        await drawLine(canvas);
        expect(await screen.findByText('Signature added.')).toBeInTheDocument();
        expect(screen.getByRole('status')).toHaveTextContent('Signature added.');
        expect(clear).toBeEnabled();
        fireEvent.click(clear);
        expect(latest.sig).toBeUndefined();
        expect(held).toHaveLength(0);
        expect(screen.getByRole('status')).toHaveTextContent('Signature cleared.');
    });

    it('a second drawing replaces the first image (a new id, one file part)', async () => {
        show();
        const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
        await drawLine(canvas);
        const first = latest.sig.signature.file_id;
        await drawLine(canvas);
        expect(latest.sig.signature.file_id).not.toBe(first);
        expect(held).toHaveLength(1);
    });

    it('a tap or a very short stroke is not a signature, and a move without a press draws nothing', async () => {
        show();
        const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
        await act(async () => {
            pointer(canvas, 'pointermove', 50, 50);
        });
        expect(latest.sig).toBeUndefined();
        await act(async () => {
            pointer(canvas, 'pointerdown', 50, 50);
            pointer(canvas, 'pointerup', 50, 50);
        });
        expect(latest.sig).toBeUndefined();
        await act(async () => {
            pointer(canvas, 'pointerdown', 50, 50);
            pointer(canvas, 'pointermove', 53, 50);
            pointer(canvas, 'pointerup', 53, 50);
        });
        expect(latest.sig).toBeUndefined();
        expect(held).toHaveLength(0);
    });

    it('draws with one pointer only: a second finger and a pen eraser draw nothing', async () => {
        show();
        const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
        await act(async () => {
            pointer(canvas, 'pointerdown', 10, 10, { pointerId: 1 });
            // a second finger lands, moves and lifts while the first draws
            pointer(canvas, 'pointerdown', 200, 80, { pointerId: 2 });
            pointer(canvas, 'pointermove', 250, 90, { pointerId: 2 });
            pointer(canvas, 'pointerup', 250, 90, { pointerId: 2 });
        });
        // the second finger lifting does not end the first stroke
        expect(latest.sig).toBeUndefined();
        await act(async () => {
            pointer(canvas, 'pointermove', 120, 40, { pointerId: 1 });
            pointer(canvas, 'pointerup', 120, 40, { pointerId: 1 });
        });
        expect(latest.sig.signature.method).toBe('drawn');
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: 'Clear signature' }));
        });
        await act(async () => {
            pointer(canvas, 'pointerdown', 10, 10, { pointerId: 3, button: 5 });
            pointer(canvas, 'pointermove', 200, 80, { pointerId: 3, button: 5 });
            pointer(canvas, 'pointerup', 200, 80, { pointerId: 3, button: 5 });
        });
        expect(latest.sig).toBeUndefined();
        expect(held).toHaveLength(0);
    });

    it('drops a PNG that is made after Clear or a switch to typing', async () => {
        let finish: (() => void) | undefined;
        vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(((cb: BlobCallback) => {
            finish = () => cb(new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: 'image/png' }));
        }) as any);
        show();
        const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
        await drawLine(canvas);
        fireEvent.click(screen.getByRole('button', { name: 'Clear signature' }));
        await act(async () => finish?.());
        expect(latest.sig).toBeUndefined();
        expect(held).toHaveLength(0);
        await drawLine(canvas);
        fireEvent.click(screen.getByRole('radio', { name: 'Type your name' }));
        fireEvent.change(await screen.findByLabelText('Your full name'), { target: { value: 'Ada' } });
        await act(async () => finish?.());
        expect(latest.sig).toEqual({ type: 'signature', signature: { method: 'typed', name: 'Ada' } });
        expect(held).toHaveLength(0);
    });

    it('types: the name is the answer, trimmed, and clearing the box removes it', async () => {
        show();
        fireEvent.click(await screen.findByRole('radio', { name: 'Type your name' }));
        const input = await screen.findByLabelText('Your full name');
        expect(input).toHaveAttribute('autocomplete', 'name');
        // 100 characters as the server counts them: the box itself only bounds UTF-16 units
        expect(input).toHaveAttribute('maxlength', '200');
        expect(input).toBeRequired();
        fireEvent.change(input, { target: { value: '  Fatima El Idrissi ' } });
        expect(latest.sig).toEqual({ type: 'signature', signature: { method: 'typed', name: 'Fatima El Idrissi' } });
        expect(held).toHaveLength(0);
        expect(checkAnswerRules(sign, latest.sig)).toEqual([]);
        // the style it will be shown in is a preview; the text is the name
        expect(screen.getByText('Fatima El Idrissi', { selector: 'p' })).toHaveAttribute('aria-hidden', 'true');
        fireEvent.change(input, { target: { value: '   ' } });
        expect(latest.sig).toBeUndefined();
    });

    it('keeps a name to 100 characters, counting a character outside the BMP as one', async () => {
        show();
        fireEvent.click(await screen.findByRole('radio', { name: 'Type your name' }));
        const input = await screen.findByLabelText('Your full name');
        fireEvent.change(input, { target: { value: '\u{1F600}'.repeat(60) + 'a'.repeat(60) } });
        expect(Array.from(latest.sig.signature.name)).toHaveLength(100);
        expect(Array.from(latest.sig.signature.name).slice(0, 60).join('')).toBe('\u{1F600}'.repeat(60));
    });

    it('flags a name with hidden characters and keeps it as typed', async () => {
        show();
        fireEvent.click(await screen.findByRole('radio', { name: 'Type your name' }));
        const input = await screen.findByLabelText('Your full name');
        fireEvent.change(input, { target: { value: 'Ada\u200bLovelace' } });
        // kept as typed, so the page flags it on Continue and the server would refuse it; it is never "fixed" silently
        expect(latest.sig.signature.name).toBe('Ada\u200bLovelace');
        expect(checkAnswerRules(sign, latest.sig)).toEqual(['FORMAT']);
        expect(screen.getByText('Your name has characters that cannot be used. Please type it again.')).toBeInTheDocument();
        expect(input).toHaveAccessibleDescription(/characters that cannot be used/);
        expect(input).toHaveAttribute('aria-invalid', 'true');
    });

    it('says the name problem once: after Continue the question owns the message', async () => {
        show();
        fireEvent.click(await screen.findByRole('radio', { name: 'Type your name' }));
        const input = await screen.findByLabelText('Your full name');
        fireEvent.change(input, { target: { value: 'Ada\u200bLovelace' } });
        expect(screen.getAllByText('Your name has characters that cannot be used. Please type it again.')).toHaveLength(1);
        act(() => flag({ sig: ['FORMAT'] }));
        expect(screen.getAllByText('Your name has characters that cannot be used. Please type it again.')).toHaveLength(1);
        expect(screen.getByRole('alert')).toHaveTextContent('characters that cannot be used');
        expect(input).toHaveAttribute('aria-invalid', 'true');
        // a fixed name clears the mark
        fireEvent.change(input, { target: { value: 'Ada Lovelace' } });
        expect(input).not.toHaveAttribute('aria-invalid');
    });

    it('marks the drawing box with the error edge while the question is flagged', async () => {
        show();
        const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
        const pad = canvas.closest('[data-signature-pad]') as HTMLElement;
        const atRest = pad.style.borderColor;
        act(() => flag({ sig: ['REQUIRED'] }));
        expect(pad.style.borderColor).not.toBe(atRest);
    });

    it('shows which way is chosen by a dot and weight, like a choice question', async () => {
        show();
        const draw = (await screen.findByRole('radio', { name: 'Draw' })).closest('label') as HTMLElement;
        const typed = screen.getByRole('radio', { name: 'Type your name' }).closest('label') as HTMLElement;
        expect(draw).toHaveClass('font-semibold');
        expect(typed).not.toHaveClass('font-semibold');
        expect(draw.querySelector('[data-choice-indicator] span')).not.toBeNull();
        expect(typed.querySelector('[data-choice-indicator] span')).toBeNull();
    });

    it('is a complete path by keyboard and screen reader: the radio, the labelled box, the question named and described', async () => {
        show();
        const typed = await screen.findByRole('radio', { name: 'Type your name' });
        typed.focus();
        expect(typed).toHaveFocus();
        fireEvent.click(typed);
        const input = await screen.findByRole('textbox', { name: /Your full name/ });
        expect(input).toHaveAccessibleDescription(/By signing you agree to the terms/);
    });

    it('moving from drawing to typing sets the drawing aside, and back brings it again', async () => {
        show();
        const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
        await drawLine(canvas);
        expect(held).toHaveLength(1);
        fireEvent.click(screen.getByRole('radio', { name: 'Type your name' }));
        // no name typed: no answer, and no file part
        expect(latest.sig).toBeUndefined();
        expect(held).toHaveLength(0);
        fireEvent.change(await screen.findByLabelText('Your full name'), { target: { value: 'Ada' } });
        expect(latest.sig.signature.method).toBe('typed');
        fireEvent.click(screen.getByRole('radio', { name: 'Draw' }));
        // the typed answer is dropped; the strokes are still there and go again
        await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 5));
        });
        expect(latest.sig.signature.method).toBe('drawn');
        expect(held).toHaveLength(1);
    });

    it('keeps a held drawing through Draw, Type and Draw again, without making a new one', async () => {
        show({ sig: { type: 'signature', signature: { method: 'drawn', file_id: 'img-held' } } }, sign, false, [{ fieldId: 'sig', fileId: 'img-held' }]);
        expect(await screen.findByRole('img', { name: 'Your drawn signature' })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('radio', { name: 'Type your name' }));
        expect(held).toHaveLength(0);
        fireEvent.click(screen.getByRole('radio', { name: 'Draw' }));
        expect(latest.sig).toEqual({ type: 'signature', signature: { method: 'drawn', file_id: 'img-held' } });
        expect(held.map((item) => item.fileId)).toEqual(['img-held']);
        expect(screen.getByRole('img', { name: 'Your drawn signature' })).toBeInTheDocument();
    });

    it('a tap on a held drawing keeps it, and drawing over it signs again', async () => {
        show({ sig: { type: 'signature', signature: { method: 'drawn', file_id: 'img-held' } } }, sign, false, [{ fieldId: 'sig', fileId: 'img-held' }]);
        await screen.findByRole('img', { name: 'Your drawn signature' });
        const canvas = screen.getByRole('img', { name: 'Signature drawing area' });
        await act(async () => {
            pointer(canvas, 'pointerdown', 50, 50);
            pointer(canvas, 'pointerup', 50, 50);
        });
        expect(latest.sig.signature.file_id).toBe('img-held');
        expect(held.map((item) => item.fileId)).toEqual(['img-held']);
        expect(screen.getByRole('img', { name: 'Your drawn signature' })).toBeInTheDocument();
        await drawLine(canvas);
        expect(latest.sig.signature.file_id).not.toBe('img-held');
        expect(held).toHaveLength(1);
        expect(held[0].fileId).toBe(latest.sig.signature.file_id);
    });

    it('shows a stored typed name, and a drawing this browser holds', async () => {
        show({ sig: { type: 'signature', signature: { method: 'typed', name: 'Ada Lovelace' } } });
        expect(await screen.findByLabelText('Your full name')).toHaveValue('Ada Lovelace');
        expect(screen.getByRole('radio', { name: 'Type your name' })).toBeChecked();
    });

    it('says drawing is unavailable when the browser has no canvas', async () => {
        vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation((() => null) as any);
        show();
        expect(await screen.findByText(/Drawing is not available in this browser/)).toBeInTheDocument();
    });

    it('is inert in the builder', async () => {
        show({}, sign, true);
        const radios = await screen.findAllByRole('radio');
        radios.forEach((radio) => expect(radio).toBeDisabled());
        const canvas = screen.getByRole('img', { name: 'Signature drawing area' });
        await act(async () => {
            pointer(canvas, 'pointerdown', 10, 10);
            pointer(canvas, 'pointerup', 10, 10);
        });
        expect(latest.sig).toBeUndefined();
    });

    it('passes axe in both ways of signing', async () => {
        const { container } = show();
        await screen.findByRole('radiogroup');
        let results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
        expect(results.violations.map((v) => v.id)).toEqual([]);
        fireEvent.click(screen.getByRole('radio', { name: 'Type your name' }));
        await screen.findByLabelText('Your full name');
        fireEvent.change(screen.getByLabelText('Your full name'), { target: { value: 'Ada' } });
        results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
        expect(results.violations.map((v) => v.id)).toEqual([]);
    });
    describe('follow-ups', () => {
        it('refuses a drawing whose PNG is over the size the server takes, tells the person, and sends nothing', async () => {
            show();
            const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
            vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(((cb: BlobCallback) => cb(new Blob([new Uint8Array(150 * 1024 + 1)], { type: 'image/png' }))) as any);
            await drawLine(canvas);
            expect(held).toHaveLength(0);
            expect(latest.sig).toBeUndefined();
            expect(screen.getByRole('alert')).toHaveTextContent('too detailed');
            // the box is empty again (clear is off) and the next stroke goes on from nothing, taking the message away
            expect(screen.getByRole('button', { name: 'Clear signature' })).toBeDisabled();
            vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(((cb: BlobCallback) => cb(new Blob([new Uint8Array(150 * 1024)], { type: 'image/png' }))) as any);
            await drawLine(canvas);
            expect(screen.queryByRole('alert')).toBeNull();
            expect(latest.sig.signature.method).toBe('drawn');
            expect(held).toHaveLength(1);
        });

        it('takes the "please answer" mark away on the first stroke, and on typed input', async () => {
            show();
            const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
            act(() => flag({ sig: ['REQUIRED'], other: ['REQUIRED'] }));
            expect(flagged.sig).toEqual(['REQUIRED']);
            await act(async () => {
                pointer(canvas, 'pointerdown', 10, 10);
            });
            // before the stroke ends: the mark of this question is gone, another question's stays
            expect(flagged.sig).toBeUndefined();
            expect(flagged.other).toEqual(['REQUIRED']);
            await act(async () => {
                pointer(canvas, 'pointerup', 10, 10);
            });
            fireEvent.click(screen.getByRole('radio', { name: 'Type your name' }));
            act(() => flag({ sig: ['REQUIRED'] }));
            fireEvent.change(screen.getByLabelText('Your full name'), { target: { value: 'A' } });
            expect(flagged.sig).toBeUndefined();
            expect(latest.sig.signature).toMatchObject({ method: 'typed', name: 'A' });
        });

        it('says a signature is on file for a drawn answer the browser does not hold (an edit), until a new one is drawn', async () => {
            show({ sig: { type: 'signature', signature: { method: 'drawn', file_id: 'img-1', signed_at: '2026-11-01T10:00:00Z' } } });
            const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
            expect(screen.getByText(/A signature is on file for this response/)).toBeInTheDocument();
            await drawLine(canvas);
            expect(screen.queryByText(/A signature is on file/)).toBeNull();
            expect(latest.sig.signature.file_id).not.toBe('img-1');
        });

        it('says nothing is on file when a drawing is held, for a typed name, or for no answer', async () => {
            show({ sig: { type: 'signature', signature: { method: 'drawn', file_id: 'img-1' } } }, sign, false, [{ fieldId: 'sig', fileId: 'img-1' }]);
            await screen.findByRole('img', { name: 'Signature drawing area' });
            expect(screen.queryByText(/A signature is on file/)).toBeNull();
        });

        it('announces "Signature added" once per drawing, not for each stroke, and again after clearing', async () => {
            show();
            const canvas = await screen.findByRole('img', { name: 'Signature drawing area' });
            const status = screen.getByRole('status');
            const seen: string[] = [];
            const watch = new MutationObserver(() => seen.push(status.textContent ?? ''));
            watch.observe(status, { childList: true, characterData: true, subtree: true });
            await drawLine(canvas);
            await drawLine(canvas);
            await act(async () => undefined);
            expect(seen.filter((text) => text === 'Signature added.')).toHaveLength(1);
            expect(status).toHaveAttribute('role', 'status');
            fireEvent.click(screen.getByRole('button', { name: 'Clear signature' }));
            await drawLine(canvas);
            await act(async () => undefined);
            watch.disconnect();
            expect(seen.filter((text) => text === 'Signature added.')).toHaveLength(2);
        });
    });
});

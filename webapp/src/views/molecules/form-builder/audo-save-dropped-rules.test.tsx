import React from 'react';

import { act, render, screen } from '@testing-library/react';
import i18n from 'i18next';
import { Provider, useAtomValue, useSetAtom } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { ToastAction } from '@app/shadcn/components/ui/toast';
import { Toaster } from '@app/shadcn/components/ui/toaster';
import { toast, toastWhenFree } from '@app/shadcn/components/ui/use-toast';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useBuilderHydration } from '@app/store/jotai/builder-hydration';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { DispatchArgs, dispatchAtom, docHistoryAtom } from '@app/store/jotai/form-document';
import { formLanguageAtom } from '@app/store/jotai/form-language';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { withoutFieldRules } from '@app/utils/field-rule-copies';

import AutoSaveForm, { droppedRulesText, newlyDroppedQuestions, resetDroppedRuleNotices } from './audo-save-form';

const patchFormMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, usePatchV2FormMutation: () => [patchFormMock] };
});
vi.mock('@app/utils/reload-page', () => ({ reloadPage: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => '/ws/dashboard/forms/form-1/edit' }));

const RULE = { id: 'r1', when: { conditions: [{ fieldId: 'gone', comparison: 'IS_EMPTY' }] }, then: { required: true } };
const KEPT = { id: 'r2', when: { conditions: [{ fieldId: 'q-1', comparison: 'IS_EMPTY' }] }, then: { required: true } };
const DROPPED = [{ fieldId: 'q-2', ruleId: 'r1', message: 'x' }];

const page = (): StandardFormFieldDto[] => [
    {
        id: 'page-1',
        index: 0,
        type: FieldTypes.SLIDE,
        properties: {
            fields: [
                { id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name', description: '' },
                { id: 'q-2', index: 1, type: FieldTypes.SHORT_TEXT, title: 'Other', description: '', properties: { rules: [RULE, KEPT] } as any }
            ]
        }
    } as StandardFormFieldDto
];

const editor: { fields?: ReturnType<typeof useFormFieldsAtom>; undoSteps?: number; dispatch?: (args: DispatchArgs) => boolean; language?: string | null } = {};

function EditorPage() {
    const fields = useFormFieldsAtom();
    const { setFormState } = useFormState();
    const { setHydratedFormId } = useBuilderHydration();
    editor.fields = fields;
    editor.undoSteps = useAtomValue(docHistoryAtom).steps.length;
    editor.dispatch = useSetAtom(dispatchAtom);
    editor.language = useAtomValue(formLanguageAtom);
    React.useEffect(() => {
        setFormState((prev) => ({ ...prev, title: 'Loaded form' }));
        fields.initFormFields(page());
        setHydratedFormId('form-1');
    }, []);
    return null;
}

const renderEditor = () => render(editorTree());
const editorTree = () => (
    <ReduxProvider store={store}>
        <Provider>
            <EditorPage />
            <AutoSaveForm formId="form-1" />
            <Toaster />
        </Provider>
    </ReduxProvider>
);

const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));
const bodyOf = (call: number) => JSON.parse(patchFormMock.mock.calls[call][0].body.get('form_body'));
const rulesOfQ2 = () => (editor.fields!.formFields[0].properties!.fields![1].properties as any)?.rules;
const NOTICE = '1 question lost a rule that no longer fits the form.';

describe('rules a save left out', () => {
    beforeEach(async () => {
        vi.useFakeTimers();
        resetDroppedRuleNotices();
        await i18n.changeLanguage('en');
        patchFormMock.mockReset();
        store.dispatch(setWorkspace({ id: 'ws-1' } as any));
        store.dispatch(setForm({ formId: 'form-1', title: 'Loaded form', updatedAt: '2026-10-30T09:00:00.000+00:00' } as any));
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('are pruned from the builder without an undo step, told once, and not sent again', async () => {
        patchFormMock.mockResolvedValueOnce({ data: { formId: 'form-1', updatedAt: '2026-10-30T09:00:01.000+00:00', droppedFieldRules: DROPPED } }).mockResolvedValue({ data: { formId: 'form-1', updatedAt: '2026-10-30T09:00:02.000+00:00' } });
        renderEditor();
        await act(async () => editor.fields!.updateDescription(0, 0, 'Your name'));
        const steps = editor.undoSteps;
        await advance(1000);
        await advance(0);
        expect(patchFormMock).toHaveBeenCalledTimes(1);
        // the builder already let go of the rule that no longer fits (its own check, as the server's), so the save does not carry it
        expect(bodyOf(0).fields[0].properties.fields[1].properties.rules.map((r: any) => r.id)).toEqual(['r2']);
        // and it keeps the other, with no extra undo step
        expect(rulesOfQ2().map((r: any) => r.id)).toEqual(['r2']);
        expect(editor.undoSteps).toBe(steps);
        expect(screen.getByText(NOTICE)).toBeTruthy();
        // letting go of it is not an edit: nothing more is saved
        await advance(5000);
        expect(patchFormMock).toHaveBeenCalledTimes(1);
        // the next edit's save no longer carries it, and no second notice
        await act(async () => editor.fields!.updateDescription(0, 0, 'Full name'));
        await advance(1000);
        await advance(0);
        expect(patchFormMock).toHaveBeenCalledTimes(2);
        expect(bodyOf(1).fields[0].properties.fields[1].properties.rules.map((r: any) => r.id)).toEqual(['r2']);
        // (the first notice has closed by now; none came back)
        expect(screen.queryByText(NOTICE)).toBeNull();
    });

    it('never replace an open Undo toast; the notice waits for it', async () => {
        patchFormMock.mockResolvedValue({ data: { formId: 'form-1', updatedAt: '2026-10-30T09:00:01.000+00:00', droppedFieldRules: DROPPED } });
        renderEditor();
        let undo: { dismiss: () => void } | undefined;
        await act(async () => {
            editor.fields!.updateDescription(0, 0, 'Your name');
            undo = toast({
                description: 'Question deleted',
                duration: 8000,
                action: <ToastAction altText="Undo the delete">Undo</ToastAction>
            });
        });
        await advance(1000);
        await advance(0);
        expect(patchFormMock).toHaveBeenCalledTimes(1);
        expect(screen.getByText('Question deleted')).toBeTruthy();
        expect(screen.getByText('Undo')).toBeTruthy();
        expect(screen.queryByText(NOTICE)).toBeNull();
        await act(async () => undo!.dismiss());
        await advance(10);
        expect(screen.getByText(NOTICE)).toBeTruthy();
    });

    it('counts questions, once per rule, in English and Dutch', async () => {
        const two = [...DROPPED, { fieldId: 'q-2', ruleId: 'r2' }, { fieldId: 'q-3', ruleId: 'r3' }];
        expect(newlyDroppedQuestions('f', two)).toBe(2);
        expect(newlyDroppedQuestions('f', two)).toBe(0);
        expect(droppedRulesText(2)).toBe('2 questions lost a rule that no longer fits the form.');
        await i18n.changeLanguage('nl');
        expect(droppedRulesText(1)).toBe('1 vraag verloor een regel die niet meer bij het formulier past.');
    });

    it('still take the language the server stored', async () => {
        renderEditor();
        await act(async () => editor.dispatch!({ ops: [{ op: 'set_form_language', language: 'de' }] }));
        patchFormMock.mockResolvedValueOnce({ data: { formId: 'form-1', updatedAt: '2026-10-30T09:00:01.000+00:00', settings: { language: 'nl' }, droppedFieldRules: DROPPED } });
        await advance(1000);
        await advance(0);
        expect(editor.language).toBe('nl');
        expect(rulesOfQ2().map((r: any) => r.id)).toEqual(['r2']);
    });

    it('are left out of a save queued while the dropping one was in flight', async () => {
        let answer: (value: unknown) => void = () => undefined;
        patchFormMock.mockImplementationOnce(() => new Promise((resolve) => (answer = resolve))).mockResolvedValue({ data: { formId: 'form-1', updatedAt: '2026-10-30T09:00:02.000+00:00' } });
        renderEditor();
        await act(async () => editor.fields!.updateDescription(0, 0, 'Your name'));
        await advance(1000);
        expect(patchFormMock).toHaveBeenCalledTimes(1);
        // an edit while that save is in flight: queued, still with the rule
        await act(async () => editor.fields!.updateDescription(0, 0, 'Full name'));
        await advance(1000);
        expect(patchFormMock).toHaveBeenCalledTimes(1);
        await act(async () => answer({ data: { formId: 'form-1', updatedAt: '2026-10-30T09:00:01.000+00:00', droppedFieldRules: DROPPED } }));
        await advance(0);
        expect(patchFormMock).toHaveBeenCalledTimes(2);
        const sent = bodyOf(1).fields[0].properties.fields;
        expect(sent[0].description).toBe('Full name');
        expect(sent[1].properties.rules.map((r: any) => r.id)).toEqual(['r2']);
    });

    it('waiting notices merge, wait again if another Undo opens, and go with the editor', async () => {
        const undo = () => toast({ description: 'Question deleted', duration: 8000, action: <ToastAction altText="Undo the delete">Undo</ToastAction> });
        const view = render(<Toaster />);
        let first: { dismiss: () => void } | undefined;
        let second: { dismiss: () => void } | undefined;
        await act(async () => {
            first = undo();
        });
        await act(async () => {
            toastWhenFree({}, { key: 'k', count: 1, describe: droppedRulesText });
            toastWhenFree({}, { key: 'k', count: 2, describe: droppedRulesText });
        });
        // the Undo closes, and another opens before the notice could show
        await act(async () => {
            first!.dismiss();
            second = undo();
        });
        await advance(10);
        expect(screen.queryByText('3 questions lost a rule that no longer fits the form.')).toBeNull();
        expect(screen.getAllByText('Undo').length).toBeGreaterThan(0);
        // once that one closes too, one notice for both
        await act(async () => second!.dismiss());
        await advance(10);
        expect(screen.getByText('3 questions lost a rule that no longer fits the form.')).toBeTruthy();
        view.unmount();
        // a notice whose page went away never shows
        const shown = render(<Toaster />);
        let cancel: () => void = () => undefined;
        await act(async () => {
            cancel = toastWhenFree({}, { key: 'other', count: 1, describe: droppedRulesText });
        });
        cancel();
        await act(async () => {
            toast({ description: 'Saved' });
        });
        await advance(10);
        expect(screen.queryByText('1 question lost a rule that no longer fits the form.')).toBeNull();
        shown.unmount();
    });

    it('a merged notice shows once the Undo is gone', async () => {
        const view = render(<Toaster />);
        let undo: { dismiss: () => void } | undefined;
        await act(async () => {
            undo = toast({ description: 'Question deleted', duration: 8000, action: <ToastAction altText="Undo the delete">Undo</ToastAction> });
            toastWhenFree({}, { key: 'm', count: 1, describe: droppedRulesText });
            toastWhenFree({}, { key: 'm', count: 1, describe: droppedRulesText });
        });
        await act(async () => undo!.dismiss());
        await advance(10);
        expect(screen.getByText('2 questions lost a rule that no longer fits the form.')).toBeTruthy();
        view.unmount();
    });

    it('withoutFieldRules leaves untouched paths alone', () => {
        const fields = page();
        expect(withoutFieldRules(fields, [])).toBe(fields);
        expect(withoutFieldRules(fields, [{ fieldId: 'q-9', ruleId: 'r1' }])).toBe(fields);
        const pruned = withoutFieldRules(fields, [
            { fieldId: 'q-2', ruleId: 'r1' },
            { fieldId: 'q-2', ruleId: 'r2' }
        ]);
        expect(pruned).not.toBe(fields);
        expect(pruned[0].properties!.fields![0]).toBe(fields[0].properties!.fields![0]);
        expect('rules' in (pruned[0].properties!.fields![1].properties as any)).toBe(false);
        // the input is not changed
        expect((fields[0].properties!.fields![1].properties as any).rules).toHaveLength(2);
    });

    it('a notice still waiting when the editor closes never shows', async () => {
        patchFormMock.mockResolvedValue({ data: { formId: 'form-1', updatedAt: '2026-10-30T09:00:01.000+00:00', droppedFieldRules: DROPPED } });
        const toaster = render(<Toaster />);
        const editorView = render(editorTree());
        let undo: { dismiss: () => void } | undefined;
        await act(async () => {
            editor.fields!.updateDescription(0, 0, 'Your name');
            undo = toast({ description: 'Question deleted', duration: 8000, action: <ToastAction altText="Undo the delete">Undo</ToastAction> });
        });
        await advance(1000);
        await advance(0);
        expect(patchFormMock).toHaveBeenCalledTimes(1);
        editorView.unmount();
        await act(async () => undo!.dismiss());
        await advance(10);
        expect(screen.queryByText(NOTICE)).toBeNull();
        toaster.unmount();
    });
});

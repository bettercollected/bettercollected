import React from 'react';

import { act, render, screen } from '@testing-library/react';
import i18n from 'i18next';
import { Provider, useAtomValue } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { ToastAction } from '@app/shadcn/components/ui/toast';
import { Toaster } from '@app/shadcn/components/ui/toaster';
import { toast } from '@app/shadcn/components/ui/use-toast';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useBuilderHydration } from '@app/store/jotai/builder-hydration';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { docHistoryAtom } from '@app/store/jotai/form-document';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { withoutFieldRules } from '@app/utils/field-rule-copies';

import AutoSaveForm, { droppedRulesNotice, resetDroppedRuleNotices } from './audo-save-form';

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

const editor: { fields?: ReturnType<typeof useFormFieldsAtom>; undoSteps?: number } = {};

function EditorPage() {
    const fields = useFormFieldsAtom();
    const { setFormState } = useFormState();
    const { setHydratedFormId } = useBuilderHydration();
    editor.fields = fields;
    editor.undoSteps = useAtomValue(docHistoryAtom).steps.length;
    React.useEffect(() => {
        setFormState((prev) => ({ ...prev, title: 'Loaded form' }));
        fields.initFormFields(page());
        setHydratedFormId('form-1');
    }, []);
    return null;
}

const renderEditor = () =>
    render(
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
        expect(bodyOf(0).fields[0].properties.fields[1].properties.rules.map((r: any) => r.id)).toEqual(['r1', 'r2']);
        // the builder lets go of the dropped rule only, with no undo step
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
        expect(droppedRulesNotice('f', two)).toBe('2 questions lost a rule that no longer fits the form.');
        expect(droppedRulesNotice('f', two)).toBeNull();
        await i18n.changeLanguage('nl');
        expect(droppedRulesNotice('f', [{ fieldId: 'q-4', ruleId: 'r4' }])).toBe('1 vraag verloor een regel die niet meer bij het formulier past.');
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
});

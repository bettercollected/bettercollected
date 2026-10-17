import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider, useAtomValue, useSetAtom } from 'jotai';
import { beforeEach, describe, expect, it } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT } from '@app/models/types/form-builder-shared';
import { Toaster } from '@app/shadcn/components/ui/toaster';
import { useActiveThankYouPageComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { docHistoryAtom, resetFromServerAtom } from '@app/store/jotai/form-document';

import { useEndingActions } from './use-ending-actions';

const loadedForm = () => ({
    formId: 'form-1',
    title: 'Eligibility',
    thankyouPage: [
        { id: 'yes', name: 'Eligible', title: 'You qualify', isDefault: true },
        { id: 'no', name: 'Not eligible', title: 'Sorry' }
    ],
    fields: [
        {
            id: 'page-1',
            index: 0,
            type: FieldTypes.SLIDE,
            properties: {
                fields: [{ id: 'q-1', index: 0, type: FieldTypes.YES_NO, title: 'Over 18?', properties: { choices: [{ id: 'c-yes', value: 'Yes' }, { id: 'c-no', value: 'No' }] } }],
                jumps: [{ operator: 'AND', target: JUMP_TARGET_SUBMIT, endingId: 'no', conditions: [{ fieldId: 'q-1', comparison: 'IS_EQUAL', value: 'No' }] }]
            }
        }
    ]
});

const seen: { actions?: ReturnType<typeof useEndingActions>; builder?: ReturnType<typeof useFormFieldsAtom>; form?: ReturnType<typeof useFormState>; ending?: ReturnType<typeof useActiveThankYouPageComponent>; steps?: number; cursor?: number } = {};

function Editor() {
    seen.actions = useEndingActions();
    seen.builder = useFormFieldsAtom();
    seen.form = useFormState();
    seen.ending = useActiveThankYouPageComponent();
    const history = useAtomValue(docHistoryAtom);
    seen.steps = history.steps.length;
    seen.cursor = history.cursor;
    const reset = useSetAtom(resetFromServerAtom);
    React.useEffect(() => reset(loadedForm() as any), []);
    return null;
}

const endingIds = () => seen.form!.formState.thankyouPage?.map((ending) => ending.id);
const jump = () => (seen.builder!.formFields[0].properties?.jumps as any[])[0];

describe('ending actions are one undo step each', () => {
    beforeEach(() => {
        render(
            <Provider>
                <Editor />
                <Toaster />
            </Provider>
        );
    });

    it('deleting an ending a jump uses: one toolbar undo brings back the ending and its jump', async () => {
        await act(async () => seen.actions!.deleteEnding(1));
        expect(endingIds()).toEqual(['yes']);
        expect(jump().endingId).toBeUndefined();
        expect(jump().target).toBe(JUMP_TARGET_SUBMIT);
        expect(seen.steps).toBe(1);

        await act(async () => seen.builder!.undo());
        expect(endingIds()).toEqual(['yes', 'no']);
        expect(jump().endingId).toBe('no');
        expect(seen.builder!.canUndo).toBe(false);

        await act(async () => seen.builder!.redo());
        expect(endingIds()).toEqual(['yes']);
        expect(jump().endingId).toBeUndefined();
    });

    it('add, duplicate, make default and rename are one step each; typing a name is one step', async () => {
        await act(async () => {
            seen.actions!.addEnding();
        });
        await act(async () => seen.actions!.duplicateEnding(0));
        await act(async () => seen.actions!.makeDefault(1));
        for (const name of ['O', 'Ok', 'Okay']) await act(async () => seen.actions!.renameEnding(0, name));
        expect(seen.steps).toBe(4);
        expect(seen.form!.formState.thankyouPage).toHaveLength(4);

        await act(async () => seen.builder!.undo());
        expect(seen.form!.formState.thankyouPage![0].name).toBe('Eligible');
        await act(async () => seen.builder!.undo());
        await act(async () => seen.builder!.undo());
        await act(async () => seen.builder!.undo());
        expect(endingIds()).toEqual(['yes', 'no']);
        expect(seen.builder!.canUndo).toBe(false);
    });

    it("the delete toast's Undo steps back: no new steps", async () => {
        await act(async () => seen.actions!.deleteEnding(1));
        await act(async () => fireEvent.click(await screen.findByRole('button', { name: 'Undo' })));
        expect(endingIds()).toEqual(['yes', 'no']);
        expect(jump().endingId).toBe('no');
        expect(seen.steps).toBe(1);
        expect(seen.cursor).toBe(0);
        expect(seen.builder!.canRedo).toBe(true);
    });

    it('undoing the add of the selected ending selects the default ending', async () => {
        await act(async () => {
            seen.actions!.addEnding();
        });
        expect(seen.ending!.activeThankYouPageComponent?.index).toBe(2);
        await act(async () => seen.builder!.undo());
        expect(seen.form!.formState.thankyouPage).toHaveLength(2);
        expect(seen.ending!.activeThankYouPageComponent?.index).toBe(0);
    });
});

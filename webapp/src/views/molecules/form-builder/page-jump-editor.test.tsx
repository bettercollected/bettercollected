import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT, LogicalOperator } from '@app/models/types/form-builder-shared';
import { useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';

import PageJumpEditor from './page-jump-editor';

const pages = (jumps?: any[]): StandardFormFieldDto[] =>
    [
        { id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'member', index: 0, type: FieldTypes.YES_NO, title: 'Member?' }], jumps } },
        { id: 'p2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [] } }
    ] as any;
const rule = (extra: Record<string, any> = {}) => ({ operator: LogicalOperator.AND, conditions: [{ fieldId: 'member', fieldType: FieldTypes.YES_NO, comparison: 'IS_EQUAL', value: 'No' }], target: JUMP_TARGET_SUBMIT, ...extra });

const seen: any = {};
function Editor({ jumps, endings }: { jumps?: any[]; endings: any[] }) {
    const builder = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setFormState } = useFormState();
    seen.builder = builder;
    React.useEffect(() => {
        builder.initFormFields(pages(jumps));
        setFormState((prev) => ({ ...prev, thankyouPage: endings }));
        setActiveSlideComponent({ id: 'p1', index: 0 });
    }, []);
    return builder.activeSlide ? <PageJumpEditor /> : null;
}

const renderEditor = async (jumps: any[] | undefined, endings: any[]) => {
    render(
        <Provider>
            <Editor jumps={jumps} endings={endings} />
        </Provider>
    );
    await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
};
const ENDINGS = [
    { id: 'thanks', name: 'Thanks' },
    { id: 'sorry', name: 'Not eligible' }
];

describe('PageJumpEditor and endings', () => {
    it('offers the default ending and every ending as destinations', async () => {
        await renderEditor([rule()], ENDINGS);
        const select = screen.getByRole('combobox', { name: 'Destination of rule 1' });
        const submitGroup = within(select).getByRole('group', { name: 'Submit and show' });
        expect(
            within(submitGroup)
                .getAllByRole('option')
                .map((o) => o.textContent)
        ).toEqual(['Submit → default ending (Thanks)', 'Submit → Thanks', 'Submit → Not eligible']);
        expect((select as HTMLSelectElement).value).toBe(JUMP_TARGET_SUBMIT);
    });

    it('stores a chosen ending beside the submit target, and clears it for a page', async () => {
        await renderEditor([rule()], ENDINGS);
        const select = screen.getByRole('combobox', { name: 'Destination of rule 1' });
        act(() => void fireEvent.change(select, { target: { value: '__ENDING__:sorry' } }));
        expect(seen.builder.formFields[0].properties.jumps[0]).toMatchObject({ target: JUMP_TARGET_SUBMIT, endingId: 'sorry' });
        expect((screen.getByRole('combobox', { name: 'Destination of rule 1' }) as HTMLSelectElement).value).toBe('__ENDING__:sorry');
        act(() => void fireEvent.change(screen.getByRole('combobox', { name: 'Destination of rule 1' }), { target: { value: 'p2' } }));
        const jump = seen.builder.formFields[0].properties.jumps[0];
        expect(jump.target).toBe('p2');
        expect(jump).not.toHaveProperty('endingId');
    });

    it('flags a jump to an ending that was deleted', async () => {
        await renderEditor([rule({ endingId: 'gone' })], ENDINGS);
        expect(screen.getByRole('option', { name: '⚠ Deleted ending — pick a target' })).toBeInTheDocument();
        expect(screen.getByText('This rule shows an ending that was deleted. Pick a new destination.')).toBeInTheDocument();
    });

    it('with one ending, offers only "submit"', async () => {
        await renderEditor([rule()], [{ title: 'Thanks' }]);
        const group = within(screen.getByRole('combobox', { name: 'Destination of rule 1' })).getByRole('group', { name: 'Submit and show' });
        expect(
            within(group)
                .getAllByRole('option')
                .map((o) => o.textContent)
        ).toEqual(['Submit → default ending (Thank you)']);
    });
});

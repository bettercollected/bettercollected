import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Toaster } from '@app/shadcn/components/ui/toaster';
import { useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import SlideOptions from '@app/views/organism/form-builder/slide-options';

import { useUndoableDelete } from './use-undoable-delete';

const pages = (): StandardFormFieldDto[] => [
    {
        id: 'page-1',
        index: 0,
        type: FieldTypes.SLIDE,
        properties: {
            fields: [
                { id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name' },
                { id: 'q-2', index: 1, type: FieldTypes.EMAIL, title: 'Email' }
            ]
        }
    } as StandardFormFieldDto,
    { id: 'page-2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'q-3', index: 0, type: FieldTypes.SHORT_TEXT, title: 'City' }] } } as StandardFormFieldDto
];

const seen: { builder?: ReturnType<typeof useFormFieldsAtom>; deletes?: ReturnType<typeof useUndoableDelete> } = {};

function Builder({ rail = false }: { rail?: boolean }) {
    const builder = useFormFieldsAtom();
    const deletes = useUndoableDelete();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    seen.builder = builder;
    seen.deletes = deletes;
    React.useEffect(() => {
        builder.initFormFields(pages());
        setActiveSlideComponent({ id: 'page-1', index: 0 });
    }, []);
    return rail && builder.formFields.length ? <SlideOptions slideIndex={1} /> : null;
}

function renderBuilder(rail = false) {
    render(
        <Provider>
            <Builder rail={rail} />
            <Toaster />
        </Provider>
    );
}

const questionIds = (page = 0) => seen.builder!.formFields[page]?.properties?.fields?.map((f) => f.id);

describe('deleting with undo', () => {
    it('a deleted question comes back with Undo in the toast', async () => {
        renderBuilder();
        await act(async () => seen.deletes!.deleteQuestion(0, 0));
        expect(questionIds()).toEqual(['q-2']);
        expect(screen.getByText('Question deleted')).toBeInTheDocument();

        await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Undo' })));
        expect(questionIds()).toEqual(['q-1', 'q-2']);
    });

    it('a deleted page comes back with its questions', async () => {
        renderBuilder();
        await act(async () => seen.deletes!.deletePage(0));
        expect(seen.builder!.formFields.map((p) => p.id)).toEqual(['page-2']);
        expect(screen.getByText('Page deleted, with 2 questions')).toBeInTheDocument();

        await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Undo' })));
        expect(seen.builder!.formFields.map((p) => p.id)).toEqual(['page-1', 'page-2']);
        expect(questionIds()).toEqual(['q-1', 'q-2']);
    });

    it('the toast never undoes a later edit instead of the delete', async () => {
        renderBuilder();
        await act(async () => seen.deletes!.deleteQuestion(0, 0));
        const undo = screen.getByRole('button', { name: 'Undo' });
        await act(async () => seen.builder!.updateFieldRequired(0, 0, true));
        await act(async () => fireEvent.click(undo));
        expect(questionIds()).toEqual(['q-2']);
        expect(seen.builder!.formFields[0].properties!.fields![0].validations?.required).toBe(true);
        expect(screen.getByText(/Use Undo in the toolbar/)).toBeInTheDocument();
    });

    it('the page rail deletes the same way: at once, with Undo', async () => {
        renderBuilder(true);
        fireEvent.click(document.querySelector('[data-state="closed"]') as Element);
        await act(async () => fireEvent.click(await screen.findByText('Delete')));
        expect(seen.builder!.formFields.map((p) => p.id)).toEqual(['page-1']);
        expect(screen.getByText('Page deleted, with 1 question')).toBeInTheDocument();
        await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Undo' })));
        expect(seen.builder!.formFields.map((p) => p.id)).toEqual(['page-1', 'page-2']);
    });
});

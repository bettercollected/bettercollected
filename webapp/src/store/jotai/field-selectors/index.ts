'use client';

import { useAtomValue, useSetAtom } from 'jotai';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { ActiveFormBuilderComponent, followSelectionAtom, useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import { CommitMeta, builderFieldsAtom, canRedoAtom, canUndoAtom, commitBuilderFieldsAtom, initBuilderFieldsAtom, redoAtom, undoAtom } from '@app/store/jotai/form-document';
import { locateField } from '@app/utils/form-outline';

import { choiceMutators } from './choices';
import { fieldMutators } from './fields';
import { groupMutators } from './groups';
import { logicMutators } from './logic';
import { pageMutators } from './pages';
import { tabularMutators } from './tabular';

export { initialFieldsState } from '@app/store/jotai/form-defaults';
export { UNDO_COALESCE_MS, undoIfLatestAtom } from '@app/store/jotai/form-document';

/**
 * The builder's pages as its mutators see them: a mutable copy of the form
 * document's pages (see form-document.ts). Exported for tests (asserting
 * what the canvas state received).
 */
export const initialFieldsAtom = builderFieldsAtom;

/** What the mutator modules share. */
export interface BuilderContext {
    formFields: StandardFormFieldDto[];
    /**
     * Hand over the edited pages: the change becomes one undo step.
     * `coalesceKey` names the text being typed (e.g. `description:<fieldId>`):
     * the latest step absorbs an edit of the same text within
     * UNDO_COALESCE_MS of the previous one. `{ undoable: false }`: no step
     * (a default written on mount).
     */
    setFormFields: (next: StandardFormFieldDto[], meta?: string | CommitMeta) => void;
    activeSlideComponent: ActiveFormBuilderComponent | null;
    setActiveSlideComponent: (value: ActiveFormBuilderComponent | null) => void;
    activeFieldComponent: ActiveFormBuilderComponent | null;
    setActiveFieldComponent: (value: ActiveFormBuilderComponent | null) => void;
    activeSlide: StandardFormFieldDto | undefined;
    activeField: StandardFormFieldDto | undefined;
    getActiveSlide: () => StandardFormFieldDto | undefined;
    reselectAfterMove: () => void;
}

export default function useFormFieldsAtom() {
    const formFields = useAtomValue(builderFieldsAtom);
    const commitFields = useSetAtom(commitBuilderFieldsAtom);
    const initFields = useSetAtom(initBuilderFieldsAtom);
    const canUndo = useAtomValue(canUndoAtom);
    const canRedo = useAtomValue(canRedoAtom);
    const undoStep = useSetAtom(undoAtom);
    const redoStep = useSetAtom(redoAtom);
    const followSelection = useSetAtom(followSelectionAtom);

    // Every mutation funnels through this setter, so each change becomes an
    // undo step (as ops on the form document). Undo/redo bypass it.
    // Unchanged states make no step.
    const setFormFields = (next: StandardFormFieldDto[], meta?: string | CommitMeta) => {
        commitFields(next, meta);
    };

    // Seed the builder with loaded fields and start undo history from there —
    // initialization must not be undoable (undoing past it would blank the form,
    // and autosave would persist the blank).
    const initFormFields = (fields: StandardFormFieldDto[]) => {
        initFields(fields);
    };

    const undo = () => {
        if (undoStep()) followSelection();
    };

    const redo = () => {
        if (redoStep()) followSelection();
    };

    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent, setActiveFieldComponent } = useActiveFieldComponent();

    const getActiveSlide = () => {
        if (activeSlideComponent?.index !== undefined) return formFields[activeSlideComponent!.index];
        return;
    };

    const activeSlide = getActiveSlide();

    const getActiveField = () => {
        if (activeFieldComponent?.index !== undefined) return activeSlide?.properties?.fields![activeFieldComponent.index];
        return;
    };
    const activeField = getActiveField();

    // After a reorder the active page/question keep their selection: their
    // ids are stable, their indexes are looked up again.
    const reselectAfterMove = () => {
        if (activeFieldComponent?.id) {
            const at = locateField(formFields, activeFieldComponent.id);
            if (at) {
                setActiveSlideComponent({ id: formFields[at.pageIndex].id, index: at.pageIndex });
                setActiveFieldComponent({ id: activeFieldComponent.id, index: at.fieldIndex });
                return;
            }
        }
        if (activeSlideComponent && activeSlideComponent.index >= 0) {
            const index = formFields.findIndex((slide) => slide.id === activeSlideComponent.id);
            if (index >= 0) setActiveSlideComponent({ id: activeSlideComponent.id, index });
        }
    };

    const ctx: BuilderContext = {
        formFields,
        setFormFields,
        activeSlideComponent,
        setActiveSlideComponent,
        activeFieldComponent,
        setActiveFieldComponent,
        activeSlide,
        activeField,
        getActiveSlide,
        reselectAfterMove
    };

    return {
        formFields,
        setFormFields,
        initFormFields,
        undo,
        redo,
        canUndo,
        canRedo,
        activeSlide,
        activeField,
        ...pageMutators(ctx),
        ...fieldMutators(ctx),
        ...choiceMutators(ctx),
        ...tabularMutators(ctx),
        ...groupMutators(ctx),
        ...logicMutators(ctx)
    };
}

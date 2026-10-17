'use client';

import { useMemo } from 'react';

import { useAtomValue, useSetAtom, useStore } from 'jotai';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { ActiveFormBuilderComponent, activeFieldAtom, activeSlideAtom, followSelectionAtom, useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
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

type Store = ReturnType<typeof useStore>;

type ContextParts = Pick<BuilderContext, 'formFields' | 'setFormFields' | 'activeSlideComponent' | 'setActiveSlideComponent' | 'activeFieldComponent' | 'setActiveFieldComponent'>;

/** The context the mutator modules work on, from the pages and the selection. */
function builderContext({ formFields, setFormFields, activeSlideComponent, setActiveSlideComponent, activeFieldComponent, setActiveFieldComponent }: ContextParts): BuilderContext {
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

    return {
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
}

/** Every mutation of the builder, over one context. */
function builderMutators(ctx: BuilderContext) {
    return {
        ...pageMutators(ctx),
        ...fieldMutators(ctx),
        ...choiceMutators(ctx),
        ...tabularMutators(ctx),
        ...groupMutators(ctx),
        ...logicMutators(ctx)
    };
}

export type BuilderMutators = ReturnType<typeof builderMutators>;

/**
 * The builder's actions without its state: the mutations of
 * useFormFieldsAtom, plus undo and redo, each reading the pages and the
 * selection when it runs. A component that only acts on the form does not
 * re-render when the form changes. Stable identity (one set per store).
 */
export interface BuilderActions extends BuilderMutators {
    /** Hand over edited pages (see BuilderContext.setFormFields). */
    setFormFields: (next: StandardFormFieldDto[], meta?: string | CommitMeta) => void;
    /** The builder's pages now (the mutable copy the mutators edit). */
    getFormFields: () => StandardFormFieldDto[];
    undo: () => void;
    redo: () => void;
}

const actionsByStore = new WeakMap<Store, BuilderActions>();

/** The builder's actions on `store` (see BuilderActions). */
export function builderActions(store: Store): BuilderActions {
    const cached = actionsByStore.get(store);
    if (cached) return cached;
    const setFormFields = (next: StandardFormFieldDto[], meta?: string | CommitMeta) => {
        store.set(commitBuilderFieldsAtom, next, meta);
    };
    const current = () =>
        builderMutators(
            builderContext({
                formFields: store.get(builderFieldsAtom),
                setFormFields,
                activeSlideComponent: store.get(activeSlideAtom),
                setActiveSlideComponent: (value) => store.set(activeSlideAtom, value),
                activeFieldComponent: store.get(activeFieldAtom),
                setActiveFieldComponent: (value) => store.set(activeFieldAtom, value)
            })
        );
    const mutators: Record<string, (...args: unknown[]) => unknown> = {};
    for (const name of Object.keys(current())) {
        mutators[name] = (...args: unknown[]) => (current() as unknown as Record<string, (...a: unknown[]) => unknown>)[name](...args);
    }
    const actions: BuilderActions = {
        ...(mutators as unknown as BuilderMutators),
        setFormFields,
        getFormFields: () => store.get(builderFieldsAtom),
        undo: () => {
            if (store.set(undoAtom)) store.set(followSelectionAtom);
        },
        redo: () => {
            if (store.set(redoAtom)) store.set(followSelectionAtom);
        }
    };
    actionsByStore.set(store, actions);
    return actions;
}

/** The builder's actions, without subscribing to the form (see BuilderActions). */
export function useBuilderActions(): BuilderActions {
    const store = useStore();
    return useMemo(() => builderActions(store), [store]);
}

/**
 * The builder's pages with its mutations. Subscribes to every change of the
 * form: a component that only acts uses useBuilderActions, one that shows a
 * page or a question the narrow hooks (store/jotai/entity-hooks.ts).
 */
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

    const ctx = builderContext({ formFields, setFormFields, activeSlideComponent, setActiveSlideComponent, activeFieldComponent, setActiveFieldComponent });

    return {
        formFields,
        setFormFields,
        initFormFields,
        undo,
        redo,
        canUndo,
        canRedo,
        activeSlide: ctx.activeSlide,
        activeField: ctx.activeField,
        ...builderMutators(ctx)
    };
}

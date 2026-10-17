'use client';

import { useSetAtom, useStore } from 'jotai';

import { DELETE_UNDO_MS } from '@app/lib/hooks/use-undoable-delete';
import { FormSlideLayout } from '@app/models/enums/form';
import { ToastAction } from '@app/shadcn/components/ui/toast';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useActiveSlideComponent, useActiveThankYouPageComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom, { undoIfLatestAtom } from '@app/store/jotai/field-selectors';
import { formStateAtom, useFormState } from '@app/store/jotai/form';
import { commitTogetherAtom, docHistoryAtom, latestStep } from '@app/store/jotai/form-document';
import { ENDING_NAME_MAX_LENGTH, Ending, MAX_ENDINGS, defaultEndingIndex, endingLabel, jumpsFallBackToDefault, newEndingId, withEndingIds } from '@app/utils/endings';

/**
 * The builder's ending actions (outline menu, properties panel): add,
 * duplicate, rename, make default and delete. A form keeps at least one
 * ending. Deleting an ending that page jumps name makes those jumps show the
 * default ending (they still submit), and the toast's Undo (the step's own
 * undo) brings the ending and those jumps back. Each action is one undo
 * step, endings and jumps together.
 */
export function useEndingActions() {
    const { toast } = useToast();
    const { formState, setFormState } = useFormState();
    const { formFields } = useFormFieldsAtom();
    const commitTogether = useSetAtom(commitTogetherAtom);
    const undoIfLatest = useSetAtom(undoIfLatestAtom);
    const { setActiveThankYouPageComponent } = useActiveThankYouPageComponent();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    // Reads the current state when an action runs (not the render's).
    const store = useStore();

    const endings: Ending[] = withEndingIds(formState.thankyouPage?.length ? formState.thankyouPage : [{ layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND }]);

    const select = (index: number) => {
        setActiveThankYouPageComponent({ id: `ending-${index}`, index });
        setActiveSlideComponent({ id: 'thank-you-page', index: -20 });
    };

    const currentEndings = (thankyouPage?: Ending[]) => withEndingIds(thankyouPage?.length ? thankyouPage : [{ layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND }]);

    // `coalesceKey`: typing a name is one undo step.
    const setEndings = (update: (current: Ending[]) => Ending[], coalesceKey?: string) => {
        setFormState((prev) => ({ ...prev, thankyouPage: update(currentEndings(prev.thankyouPage)) }), coalesceKey);
    };

    const canAdd = endings.length < MAX_ENDINGS;

    const addEnding = () => {
        const index = endings.length;
        if (!canAdd) return -1;
        setEndings((current) => [...current, { id: newEndingId(), layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND }]);
        select(index);
        return index;
    };

    const duplicateEnding = (index: number) => {
        const source = endings[index];
        if (!source || !canAdd) return;
        const name = source.name?.trim() ? `${source.name.trim()} (copy)`.slice(0, ENDING_NAME_MAX_LENGTH) : undefined;
        setEndings((current) => {
            const copy: Ending = { ...JSON.parse(JSON.stringify(current[index] ?? source)), id: newEndingId(), name, isDefault: undefined };
            return [...current.slice(0, index + 1), copy, ...current.slice(index + 1)];
        });
        select(index + 1);
    };

    const renameEnding = (index: number, name: string) => {
        const trimmed = name.slice(0, ENDING_NAME_MAX_LENGTH);
        setEndings((current) => current.map((ending, i) => (i === index ? { ...ending, name: trimmed.trim() ? trimmed : undefined } : ending)), `ending:${endings[index]?.id ?? index}:name`);
    };

    const makeDefault = (index: number) => {
        setEndings((current) => current.map((ending, i) => ({ ...ending, isDefault: i === index ? true : undefined })));
    };

    const deleteEnding = (index: number) => {
        if (endings.length <= 1) return;
        const removed = endings[index];
        if (!removed) return;
        const label = endingLabel(removed, index, endings.length);
        const fallback = removed.id ? jumpsFallBackToDefault(formFields ?? [], removed.id) : null;
        // Endings stored before they had ids get them first (not an edit), so
        // that undoing the delete brings back the ids the jumps name.
        if ((store.get(formStateAtom).thankyouPage ?? []).some((ending) => !ending?.id)) setFormState((prev) => ({ ...prev, thankyouPage: currentEndings(prev.thankyouPage) }), { undoable: false });
        // One undo step: the jumps let go of the ending, then it goes.
        const before = latestStep(store.get(docHistoryAtom));
        commitTogether({
            fields: fallback?.slides,
            formValues: { thankyouPage: currentEndings(store.get(formStateAtom).thankyouPage).filter((ending) => ending.id !== removed.id) },
            fieldsFirst: true,
            label: 'Delete ending'
        });
        const after = latestStep(store.get(docHistoryAtom));
        const step = after !== before ? after : null;
        // Stay on the endings: show the one respondents now see by default.
        const remaining = endings.filter((ending) => ending.id !== removed.id);
        select(Math.max(0, defaultEndingIndex(remaining)));

        const count = fallback?.count ?? 0;
        toast({
            description: count ? `${label} deleted. ${count} jump${count === 1 ? ' now shows' : 's now show'} the default ending.` : `${label} deleted`,
            duration: DELETE_UNDO_MS,
            action: (
                <ToastAction
                    altText="Undo deleting the ending"
                    onClick={() => {
                        // The step's own undo: the ending and its jumps come back together.
                        if (undoIfLatest(step)) select(index);
                        else toast({ description: 'You changed the form since. Use Undo in the toolbar to step back.' });
                    }}
                >
                    Undo
                </ToastAction>
            )
        });
    };

    return { endings, canAdd, addEnding, duplicateEnding, renameEnding, makeDefault, deleteEnding };
}

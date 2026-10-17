'use client';

import { useSetAtom, useStore } from 'jotai';

import { ToastAction } from '@app/shadcn/components/ui/toast';
import { toast } from '@app/shadcn/components/ui/use-toast';
import { undoIfLatestAtom, useBuilderActions } from '@app/store/jotai/field-selectors';
import { HistoryStep, docHistoryAtom, latestStep } from '@app/store/jotai/form-document';

/** How long the "… deleted · Undo" toast stays. */
export const DELETE_UNDO_MS = 8000;

/**
 * The builder's one pattern for deleting a question or a page: delete at
 * once, then offer "Undo" in a toast (Undo in the toolbar works too).
 */
export function useUndoableDelete() {
    const undoIfLatest = useSetAtom(undoIfLatestAtom);
    // Acts on the form as it is when a delete runs; never subscribes to it.
    const { getFormFields, deleteField, deleteSlide } = useBuilderActions();
    const store = useStore();

    /** Run a delete and return the undo step it made (null when none). */
    const stepOf = (remove: () => unknown): HistoryStep | null => {
        const before = latestStep(store.get(docHistoryAtom));
        remove();
        const after = latestStep(store.get(docHistoryAtom));
        return after !== before ? after : null;
    };

    // The toast undoes only that step, and only while it is the latest.
    const offerUndo = (message: string, deleted: HistoryStep | null) => {
        toast({
            description: message,
            duration: DELETE_UNDO_MS,
            action: (
                <ToastAction
                    altText="Undo the delete"
                    onClick={() => {
                        if (!undoIfLatest(deleted)) toast({ description: 'You changed the form since. Use Undo in the toolbar to step back.' });
                    }}
                >
                    Undo
                </ToastAction>
            )
        });
    };

    const deleteQuestion = (slideIndex: number, fieldIndex: number) => {
        offerUndo('Question deleted', stepOf(() => deleteField(slideIndex, fieldIndex)));
    };

    const deletePage = (slideIndex: number) => {
        const questions = getFormFields()?.[slideIndex]?.properties?.fields?.length ?? 0;
        const message = questions > 0 ? `Page deleted, with ${questions} question${questions === 1 ? '' : 's'}` : 'Page deleted';
        offerUndo(message, stepOf(() => deleteSlide(slideIndex)));
    };

    return { deleteQuestion, deletePage };
}

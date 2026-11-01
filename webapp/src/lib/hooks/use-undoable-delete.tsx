'use client';

import { useSetAtom, useStore } from 'jotai';
import { useTranslation } from 'react-i18next';

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
    const { t } = useTranslation('builder');
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
                    altText={t('TOASTS.UNDO_DELETE')}
                    onClick={() => {
                        if (!undoIfLatest(deleted)) toast({ description: t('TOASTS.CHANGED_SINCE') });
                    }}
                >
                    {t('TOASTS.UNDO')}
                </ToastAction>
            )
        });
    };

    const deleteQuestion = (slideIndex: number, fieldIndex: number) => {
        offerUndo(t('TOASTS.QUESTION_DELETED'), stepOf(() => deleteField(slideIndex, fieldIndex)));
    };

    const deletePage = (slideIndex: number) => {
        const questions = getFormFields()?.[slideIndex]?.properties?.fields?.length ?? 0;
        const message = questions > 0 ? t('TOASTS.PAGE_DELETED_WITH', { count: questions }) : t('TOASTS.PAGE_DELETED');
        offerUndo(message, stepOf(() => deleteSlide(slideIndex)));
    };

    return { deleteQuestion, deletePage };
}

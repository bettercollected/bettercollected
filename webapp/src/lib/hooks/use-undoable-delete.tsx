'use client';

import { useSetAtom } from 'jotai';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { ToastAction } from '@app/shadcn/components/ui/toast';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import useFormFieldsAtom, { undoIfLatestAtom } from '@app/store/jotai/field-selectors';

/** How long the "… deleted · Undo" toast stays. */
export const DELETE_UNDO_MS = 8000;

/**
 * The builder's one pattern for deleting a question or a page: delete at
 * once, then offer "Undo" in a toast (Undo in the toolbar works too).
 */
export function useUndoableDelete() {
    const { toast } = useToast();
    const undoIfLatest = useSetAtom(undoIfLatestAtom);
    const { formFields, deleteField, deleteSlide } = useFormFieldsAtom();

    const offerUndo = (message: string, after: StandardFormFieldDto[]) => {
        // Serialized now: the builder edits its objects in place later.
        const deleted = JSON.stringify(after);
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
        offerUndo('Question deleted', deleteField(slideIndex, fieldIndex));
    };

    const deletePage = (slideIndex: number) => {
        const questions = formFields?.[slideIndex]?.properties?.fields?.length ?? 0;
        const message = questions > 0 ? `Page deleted, with ${questions} question${questions === 1 ? '' : 's'}` : 'Page deleted';
        offerUndo(message, deleteSlide(slideIndex));
    };

    return { deleteQuestion, deletePage };
}

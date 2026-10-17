'use client';

import { useSetAtom, useStore } from 'jotai';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { ToastAction } from '@app/shadcn/components/ui/toast';
import { toast } from '@app/shadcn/components/ui/use-toast';
import { followActiveFieldAtom } from '@app/store/jotai/active-builder-component';
import { undoIfLatestAtom, useBuilderActions } from '@app/store/jotai/field-selectors';
import { HistoryStep, docHistoryAtom, latestStep } from '@app/store/jotai/form-document';
import { locateField, outlinePageName } from '@app/utils/form-outline';

/** How long the "rules removed · Undo" toast stays (same as a delete's). */
const MOVE_UNDO_MS = 8000;

type MoveResult = { next: StandardFormFieldDto[]; prunedReferences: number } | null;

/** What a move did: a sentence for the live region, and the page the item is now on. */
export type MoveOutcome = { message: string; pageId: string } | null;

/**
 * Outline moves (drag, keyboard and menu all end here). Each returns where
 * the item went (a sentence for the outline's live region, and its page),
 * or null when nothing moved. When a move removed logic that the new order
 * turned around, a toast says so and offers Undo (the toolbar's Undo works
 * too).
 */
export function useOutlineMoves() {
    // Moves read the form when they run; the outline does not re-render for them.
    const { getFormFields, movePage, moveFieldToPage } = useBuilderActions();
    const undoIfLatest = useSetAtom(undoIfLatestAtom);
    const followActiveField = useSetAtom(followActiveFieldAtom);
    const store = useStore();

    /** Run a move; also say which undo step it made (null when none). */
    const withStep = (move: () => MoveResult): [MoveResult, HistoryStep | null] => {
        const before = latestStep(store.get(docHistoryAtom));
        const result = move();
        const after = latestStep(store.get(docHistoryAtom));
        return [result, after !== before ? after : null];
    };

    const offerUndo = (result: MoveResult, after: HistoryStep | null) => {
        if (!result?.prunedReferences) return;
        const count = result.prunedReferences;
        toast({
            description: `Moved. ${count} logic rule${count === 1 ? '' : 's'} that would now use a later answer ${count === 1 ? 'was' : 'were'} removed.`,
            duration: MOVE_UNDO_MS,
            action: (
                <ToastAction
                    altText="Undo the move"
                    onClick={() => {
                        if (undoIfLatest(after)) followActiveField();
                        else toast({ description: 'You changed the form since. Use Undo in the toolbar to step back.' });
                    }}
                >
                    Undo
                </ToastAction>
            )
        });
    };

    const describeQuestion = (fieldId: string, slides: StandardFormFieldDto[]): MoveOutcome => {
        const at = locateField(slides, fieldId);
        if (!at) return null;
        const page = slides[at.pageIndex];
        const count = page.properties?.fields?.length ?? 0;
        return { message: `Moved to ${outlinePageName(page, at.pageIndex)}, position ${at.fieldIndex + 1} of ${count}.`, pageId: page.id };
    };

    const movePageTo = (from: number, to: number): MoveOutcome => {
        const [result, step] = withStep(() => movePage(from, to));
        if (!result) return null;
        offerUndo(result, step);
        return { message: `Page moved to position ${to + 1} of ${result.next.length}.`, pageId: result.next[to].id };
    };

    const moveQuestion = (fieldId: string, toPageIndex: number, toIndex: number): MoveOutcome => {
        const [result, step] = withStep(() => moveFieldToPage(fieldId, toPageIndex, toIndex));
        if (!result) return null;
        offerUndo(result, step);
        return describeQuestion(fieldId, result.next);
    };

    /** One step up; from the top of a page, to the end of the page above. */
    const moveQuestionUp = (fieldId: string): MoveOutcome => {
        const formFields = getFormFields();
        const at = locateField(formFields, fieldId);
        if (!at) return null;
        if (at.fieldIndex > 0) return moveQuestion(fieldId, at.pageIndex, at.fieldIndex - 1);
        if (at.pageIndex === 0) return null;
        return moveQuestion(fieldId, at.pageIndex - 1, formFields[at.pageIndex - 1].properties?.fields?.length ?? 0);
    };

    /** One step down; from the end of a page, to the top of the page below. */
    const moveQuestionDown = (fieldId: string): MoveOutcome => {
        const formFields = getFormFields();
        const at = locateField(formFields, fieldId);
        if (!at) return null;
        const count = formFields[at.pageIndex].properties?.fields?.length ?? 0;
        if (at.fieldIndex < count - 1) return moveQuestion(fieldId, at.pageIndex, at.fieldIndex + 1);
        if (at.pageIndex >= formFields.length - 1) return null;
        return moveQuestion(fieldId, at.pageIndex + 1, 0);
    };

    return { movePageTo, moveQuestion, moveQuestionUp, moveQuestionDown };
}

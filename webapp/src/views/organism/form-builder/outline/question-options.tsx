import { useRef } from 'react';

import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { ArrowDown, ArrowUp, Ellipsis, FileInput } from 'lucide-react';

import { DropdownMenuContent, DropdownMenuItem, DropdownMenuPortal, DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger } from '@app/shadcn/components/ui/dropdown-menu';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { outlinePageName } from '@app/utils/form-outline';

import { outlineMenuItemClass, outlineMenuTriggerClass } from '../slide-options';
import { MoveOutcome, useOutlineMoves } from './use-outline-moves';

/**
 * A question's "…" menu in the outline: the keyboard and pointer
 * alternative to dragging. Up/down cross page boundaries (from the top of a
 * page to the end of the one above); "Move to page" puts it at the end.
 */
export default function QuestionOptions({
    fieldId,
    title,
    pageIndex,
    fieldIndex,
    visible,
    onMoved
}: {
    fieldId: string;
    title: string;
    pageIndex: number;
    fieldIndex: number;
    visible: boolean;
    onMoved: (outcome: MoveOutcome) => void;
}) {
    const { formFields } = useFormFieldsAtom();
    const { moveQuestion, moveQuestionUp, moveQuestionDown } = useOutlineMoves();
    const moved = useRef(false);
    const run = (move: () => MoveOutcome) => {
        moved.current = true;
        onMoved(move());
    };
    const isLastOnPage = fieldIndex >= (formFields[pageIndex]?.properties?.fields?.length ?? 0) - 1;

    return (
        <DropdownMenuPrimitive.Root>
            <DropdownMenuPrimitive.Trigger aria-label={`Options for question: ${title}`} className={outlineMenuTriggerClass(visible)}>
                <Ellipsis className="h-4 w-4" aria-hidden="true" />
            </DropdownMenuPrimitive.Trigger>
            <DropdownMenuContent
                side="right"
                align="start"
                className="w-[220px] bg-white"
                onCloseAutoFocus={(event) => {
                    if (moved.current) event.preventDefault();
                    moved.current = false;
                }}
            >
                <DropdownMenuItem className={outlineMenuItemClass} disabled={pageIndex === 0 && fieldIndex === 0} onSelect={() => run(() => moveQuestionUp(fieldId))}>
                    <ArrowUp className="h-4 w-4" aria-hidden="true" />
                    Move up
                </DropdownMenuItem>
                <DropdownMenuItem className={outlineMenuItemClass} disabled={pageIndex >= formFields.length - 1 && isLastOnPage} onSelect={() => run(() => moveQuestionDown(fieldId))}>
                    <ArrowDown className="h-4 w-4" aria-hidden="true" />
                    Move down
                </DropdownMenuItem>
                {formFields.length > 1 && (
                    <DropdownMenuSub>
                        <DropdownMenuSubTrigger className={outlineMenuItemClass}>
                            <FileInput className="h-4 w-4" aria-hidden="true" />
                            Move to page…
                        </DropdownMenuSubTrigger>
                        <DropdownMenuPortal>
                            <DropdownMenuSubContent className="max-h-[320px] w-[220px] overflow-y-auto">
                                {formFields.map((slide, index) =>
                                    index === pageIndex ? null : (
                                        <DropdownMenuItem key={slide.id} className={outlineMenuItemClass} onSelect={() => run(() => moveQuestion(fieldId, index, slide.properties?.fields?.length ?? 0))}>
                                            <span className="text-black-600 w-5 shrink-0 text-xs tabular-nums">{index + 1}</span>
                                            <span className="truncate">{outlinePageName(slide, index)}</span>
                                        </DropdownMenuItem>
                                    )
                                )}
                            </DropdownMenuSubContent>
                        </DropdownMenuPortal>
                    </DropdownMenuSub>
                )}
            </DropdownMenuContent>
        </DropdownMenuPrimitive.Root>
    );
}

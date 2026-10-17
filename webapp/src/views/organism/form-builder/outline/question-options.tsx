import { useRef } from 'react';

import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { ArrowDown, ArrowUp, Ellipsis, FileInput } from 'lucide-react';

import { jsonEqual } from '@app/lib/form-ops/model';
import { DropdownMenuContent, DropdownMenuItem, DropdownMenuPortal, DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger } from '@app/shadcn/components/ui/dropdown-menu';
import { useDocValue } from '@app/store/jotai/entity-hooks';
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
    pageCount,
    pageFieldCount,
    visible,
    onMoved
}: {
    fieldId: string;
    title: string;
    pageIndex: number;
    fieldIndex: number;
    /** How many pages the form has. */
    pageCount: number;
    /** How many questions the question's page has. */
    pageFieldCount: number;
    visible: boolean;
    onMoved: (outcome: MoveOutcome) => void;
}) {
    const { moveQuestion, moveQuestionUp, moveQuestionDown } = useOutlineMoves();
    const moved = useRef(false);
    const run = (move: () => MoveOutcome) => {
        moved.current = true;
        onMoved(move());
    };
    const isLastOnPage = fieldIndex >= pageFieldCount - 1;

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
                <DropdownMenuItem className={outlineMenuItemClass} disabled={pageIndex >= pageCount - 1 && isLastOnPage} onSelect={() => run(() => moveQuestionDown(fieldId))}>
                    <ArrowDown className="h-4 w-4" aria-hidden="true" />
                    Move down
                </DropdownMenuItem>
                {pageCount > 1 && (
                    <DropdownMenuSub>
                        <DropdownMenuSubTrigger className={outlineMenuItemClass}>
                            <FileInput className="h-4 w-4" aria-hidden="true" />
                            Move to page…
                        </DropdownMenuSubTrigger>
                        <DropdownMenuPortal>
                            <DropdownMenuSubContent className="max-h-[320px] w-[220px] overflow-y-auto">
                                <MoveToPageItems pageIndex={pageIndex} onPick={(index, count) => run(() => moveQuestion(fieldId, index, count))} />
                            </DropdownMenuSubContent>
                        </DropdownMenuPortal>
                    </DropdownMenuSub>
                )}
            </DropdownMenuContent>
        </DropdownMenuPrimitive.Root>
    );
}

/** The other pages, while the "Move to page" submenu is open: a question goes to the end of the one picked. */
function MoveToPageItems({ pageIndex, onPick }: { pageIndex: number; onPick: (index: number, count: number) => void }) {
    const pages = useDocValue((doc) => (doc.fields ?? []).map((slide, index) => ({ id: slide.id, name: outlinePageName(slide, index), count: slide.properties?.fields?.length ?? 0 })), [], jsonEqual);
    return (
        <>
            {pages.map((page, index) =>
                index === pageIndex ? null : (
                    <DropdownMenuItem key={page.id} className={outlineMenuItemClass} onSelect={() => onPick(index, page.count)}>
                        <span className="text-black-600 w-5 shrink-0 text-xs tabular-nums">{index + 1}</span>
                        <span className="truncate">{page.name}</span>
                    </DropdownMenuItem>
                )
            )}
        </>
    );
}

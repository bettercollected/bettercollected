import Divider from '@Components/common/divider';
import { ChevronDown, ChevronUp } from 'lucide-react';

import { jsonEqual } from '@app/lib/form-ops/model';
import { useDocValue } from '@app/store/jotai/entity-hooks';
import { useBuilderActions } from '@app/store/jotai/field-selectors';
import { locateField } from '@app/utils/form-outline';

const BUTTON = 'flex items-center justify-center hover:bg-black-400 hover:text-white focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[#123FC9]';

/** Move a question up or down on its page, found by id (where it is now, not where it was rendered). */
export default function MoveUpDown({ fieldId }: { fieldId: string }) {
    const { moveFieldInASlide } = useBuilderActions();
    // Where the question is and how many its page has; a new value only when that changes.
    const at = useDocValue(
        (doc) => {
            const found = locateField(doc.fields ?? [], fieldId);
            return found ? { ...found, count: doc.fields?.[found.pageIndex]?.properties?.fields?.length ?? 0 } : null;
        },
        [fieldId],
        jsonEqual
    );

    if (!at || at.count <= 1) {
        return null;
    }

    const canMoveUp = at.fieldIndex > 0;
    const canMoveDown = at.fieldIndex !== at.count - 1;

    return (
        <div className="relative flex flex-col rounded border border-black-400" role="group" aria-label="Question order">
            {canMoveUp && (
                <button type="button" aria-label="Move question up" aria-keyshortcuts="Alt+ArrowUp" title="Move up (Alt+↑)" className={BUTTON} onClick={() => moveFieldInASlide(at.pageIndex, at.fieldIndex, at.fieldIndex - 1)}>
                    <ChevronUp aria-hidden="true" />
                </button>
            )}
            {canMoveUp && canMoveDown && <Divider />}
            {canMoveDown && (
                <button type="button" aria-label="Move question down" aria-keyshortcuts="Alt+ArrowDown" title="Move down (Alt+↓)" className={BUTTON} onClick={() => moveFieldInASlide(at.pageIndex, at.fieldIndex, at.fieldIndex + 1)}>
                    <ChevronDown aria-hidden="true" />
                </button>
            )}
        </div>
    );
}

import Divider from '@Components/common/divider';
import { ChevronDown, ChevronUp } from 'lucide-react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useDocValue } from '@app/store/jotai/entity-hooks';
import { useBuilderActions } from '@app/store/jotai/field-selectors';

const BUTTON = 'flex items-center justify-center hover:bg-black-400 hover:text-white focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[#123FC9]';

export default function MoveUpDown({ field, slideIndex }: { field: StandardFormFieldDto; slideIndex: number }) {
    const { moveFieldInASlide } = useBuilderActions();
    // Count fields on the slide this control belongs to. Reading the global
    // `activeSlide` crashed here: a field can be active while no slide is marked
    // active, leaving `activeSlide` undefined.
    const numberOfFieldsInCurrentSlide = useDocValue((doc) => doc.fields?.[slideIndex]?.properties?.fields?.length ?? 0, [slideIndex]);

    if (numberOfFieldsInCurrentSlide <= 1) {
        return null;
    }

    const canMoveUp = field.index > 0;
    const canMoveDown = field.index !== numberOfFieldsInCurrentSlide - 1;

    return (
        <div className="relative flex flex-col rounded border border-black-400" role="group" aria-label="Question order">
            {canMoveUp && (
                <button type="button" aria-label="Move question up" aria-keyshortcuts="Alt+ArrowUp" title="Move up (Alt+↑)" className={BUTTON} onClick={() => moveFieldInASlide(slideIndex, field.index, field.index - 1)}>
                    <ChevronUp aria-hidden="true" />
                </button>
            )}
            {canMoveUp && canMoveDown && <Divider />}
            {canMoveDown && (
                <button type="button" aria-label="Move question down" aria-keyshortcuts="Alt+ArrowDown" title="Move down (Alt+↓)" className={BUTTON} onClick={() => moveFieldInASlide(slideIndex, field.index, field.index + 1)}>
                    <ChevronDown aria-hidden="true" />
                </button>
            )}
        </div>
    );
}

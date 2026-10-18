import type { KeyboardEvent } from 'react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { scrollToDivById } from '@app/utils/scroll-utils';

/**
 * Enter in a one-line answer moves on to the next question on the page (the
 * last one stays put). The inputs used to sit in a form of their own for
 * this, and each of those unnamed forms made screen readers announce "end
 * of form" after every question; a key handler does the same without them.
 */
export function useEnterToNextQuestion(field: StandardFormFieldDto) {
    const form = useAppSelector(selectForm);
    const { currentSlide } = useResponderState();

    const next = () => {
        const fields = form?.fields?.[currentSlide]?.properties?.fields;
        if (fields?.length !== field.index + 1) scrollToDivById(fields?.[field.index + 1]?.id);
    };

    return (event: KeyboardEvent<HTMLElement>) => {
        // Not while an input method is composing (Enter confirms the text).
        if (event.key !== 'Enter' || event.nativeEvent.isComposing) return;
        event.preventDefault();
        next();
    };
}

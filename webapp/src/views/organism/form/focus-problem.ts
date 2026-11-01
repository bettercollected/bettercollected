import { flushSync } from 'react-dom';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import type { StandardFormFieldDto } from '@app/models/dtos/form';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useRevealQuestion } from '@app/store/jotai/responder-layout-state';
import { parseScopedFieldId } from '@app/utils/repeating-groups';
import { focusQuestionInGroup, scrollToDivById } from '@app/utils/scroll-utils';

/**
 * Bring a question with a problem into focus: where a layout container hides
 * it (a closed panel, another tab) the container opens first, says so, and
 * focus goes to the question once it is shown. `page` is the page the
 * question is on, `key` the invalid-field key (a question's id, or a scoped
 * `<child id>::<index>` inside a repeating group).
 */
export default function useFocusProblem() {
    const { t } = useRespondentLanguage();
    const formId = useAppSelector(selectResponderForm)?.formId;
    const reveal = useRevealQuestion(formId, (kind, title) => t(kind === 'panel' ? 'LAYOUT.OPENED' : 'LAYOUT.SHOWING_TAB', { title }));
    return (page: StandardFormFieldDto | undefined, key: string) => {
        // the render that shows the question has to finish before focus can land on it
        flushSync(() => reveal(page, key));
        if (parseScopedFieldId(key)) focusQuestionInGroup(key);
        else scrollToDivById(key, undefined, { focusControl: true });
    };
}

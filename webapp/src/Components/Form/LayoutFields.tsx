import React from 'react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { selectAnswers } from '@app/store/fill-form/slice';
import { useAppSelector } from '@app/store/hooks';
import { contentEditableClassNames } from '@app/utils/formBuilderBlockUtils';
import { getValueToCompareBasedOnFieldType } from '@app/utils/validationUtils';

export default function LayoutFields({ field, enabled, fields }: { field: StandardFormFieldDto; enabled: boolean; fields?: Array<StandardFormFieldDto> }) {
    const answers = useAppSelector(selectAnswers);
    const getValueWithMentionIfExists = () => {
        const placeholderRegex = /{{\s*([0-9a-fA-F-]+)\s*}}/g;

        return field?.value?.replace(placeholderRegex, (match, fieldId) => {
            const fieldAnswer = answers[fieldId];
            const answerValue = getValueToCompareBasedOnFieldType(fieldAnswer, fields?.find((field) => field.id === fieldId)?.type);
            return answerValue ?? field?.properties?.mentions?.[fieldId] ?? '';
        });
    };

    return <div className={contentEditableClassNames(false, field?.type, enabled) + ' mt-6 '}>{getValueWithMentionIfExists()}</div>;
}

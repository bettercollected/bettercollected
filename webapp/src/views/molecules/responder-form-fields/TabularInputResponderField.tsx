'use client';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import TabularInputField from '@app/views/organism/form-builder/fields/TabularInputField';
import QuestionWrapper from './question-wrapper';

export default function TabularInputResponderField({ field }: { field: StandardFormFieldDto }) {
    const { formResponse, addFieldTabularAnswer } = useFormResponse();

    const rowTitles = field?.properties?.rowTitles || [];
    const columnTitles = field?.properties?.columnTitles || [];

    // Get existing answer or fall back to field's default value
    const value = formResponse?.answers?.[field.id]?.tabular_value
        ?? field?.properties?.tabular_value
        ?? [];

    return (
        <QuestionWrapper field={field}>
            <TabularInputField
                value={value}
                onChange={(val) => addFieldTabularAnswer(field.id, val)}
                rowTitles={rowTitles}
                columnTitles={columnTitles}
                field={field}
            />
        </QuestionWrapper>
    );
}
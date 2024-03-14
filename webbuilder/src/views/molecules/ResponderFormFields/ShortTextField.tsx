import { FormField } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';

import QuestionWrapper from './QuestionQwrapper';

export default function ShortTextField ({ field }: { field: FormField }) {
    const { addFieldTextAnswer } = useFormResponse();

    return (
        <QuestionWrapper field={field}>
            <FieldInput
                type="text"
                placeholder={field?.properties?.placeholder}
                className="mt-4"
                onChange={(e: any) => addFieldTextAnswer(field.id, e.target.value)}
            />
        </QuestionWrapper>
    );
}

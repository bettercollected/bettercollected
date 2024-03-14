import { FormField } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';

import QuestionWrapper from './QuestionQwrapper';

const EmailField = ({ field }: { field: FormField }) => {
    const { addFieldEmailAnswer } = useFormResponse();

    return (
        <QuestionWrapper field={field}>
            <FieldInput
                type="email"
                placeholder={field?.properties?.placeholder}
                $slide={field}
                onChange={(e: any) => addFieldEmailAnswer(field.id, e.target.value)}
            />
        </QuestionWrapper>
    );
};

export default EmailField;

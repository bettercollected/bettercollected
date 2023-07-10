import { QUESTION_TYPE } from '@app/components/form/renderer/form-renderer';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

export interface FormFieldState {
    id: string;
    title?: string;
    description?: string;
    value?: string;
    type?: QUESTION_TYPE;
    tag: FormBuilderTagNames;
    index?: number;
    properties?: {
        steps?: number;
        placeholder?: string;
        hidden?: boolean;
        allowMultipleSelection?: boolean;
        choices?: {
            [choiceId: string]: {
                id: string;
                value?: string;
            };
        };
    };
    isFocused?: boolean;
    choices?: {};
    validations?: {
        required: boolean;
    };
}

export interface FormState {
    formId: string;
    title: string;
    description?: string;
    responseOwnerField?: string;
    fields: {
        [questionId: string]: FormFieldState;
    };
}

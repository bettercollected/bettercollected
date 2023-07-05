import { QUESTION_TYPE } from '@app/components/form/renderer/form-renderer';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

export interface FormFieldState {
    id: string;
    title: string;
    description?: string;
    value?: string;
    type: QUESTION_TYPE;
    tag?: FormBuilderTagNames;
    properties?: {
        steps?: number;
        placeholder?: string;
        hidden?: boolean;
    };
    choices?: {};
    validations?: {
        required: boolean;
    };
}

export interface FormState {
    title: string;
    description?: string;
    responseOwnerField?: string;
    fields: {
        [questionId: string]: FormFieldState;
    };
}

import { QUESTION_TYPE } from '@app/components/form/renderer/form-renderer';

export interface FormFieldState {
    id: string;
    title: string;
    description?: string;
    type: QUESTION_TYPE;
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

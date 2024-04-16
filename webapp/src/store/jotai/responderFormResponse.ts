import { set } from 'lodash';

import { atom, useAtom } from 'jotai';

import { FileMetadata } from '@app/models/types/fieldTypes';
import { Invalidations } from '@app/utils/validationUtils';

enum AnswerType {
    TEXT = 'text',
    CHOICE = 'choice',
    CHOICES = 'choices',
    NUMBER = 'number',
    BOOLEAN = 'boolean',
    MATRIX = 'matrix',
    EMAIL = 'email',
    DATE = 'date',
    URL = 'url',
    PHONE_NUMBER = 'phone_number',
    FILE_URL = 'file_url',
    PAYMENT = 'payment',
    FILE_UPLOAD = 'file_upload',
    RATING = 'rating',
    LINEAR_RATING = 'linear_rating'
}

export interface ChoicesAnswer {
    values?: Array<string>;
    other?: string;
}

export interface ChoiceAnswer {
    value?: string;
    other?: string;
}

export interface ChoicesAnswer {
    values?: Array<string>;
    other?: string;
}

export interface FormResponse {
    formId: string;
    answers: {
        [fieldId: string]: {
            type: AnswerType;
            text?: string;
            number?: number;
            email?: string;
            date?: string;
            phone_number?: string;
            url?: string;
            choice?: ChoiceAnswer;
            choices?: ChoicesAnswer;
            boolean?: boolean;
            file_metadata?: FileMetadata;
        };
    };
    consent?: Array<any>;
    invalidFields?: Record<string, Array<Invalidations>>;
    anonymize?: boolean;
}

const initialFormResponse: FormResponse = {
    formId: '',
    answers: {},
    anonymize: false
};

const formResponseAtom = atom<FormResponse>(initialFormResponse);

export const useFormResponse = () => {
    const [formResponse, setFormResponse] = useAtom(formResponseAtom);

    const addFieldTextAnswer = (fieldId: string, text: string) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.TEXT,
                    text: text
                }
            }
        });
    };

    const addFieldChoiceAnswer = (fieldId: string, choice: string) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.CHOICE,
                    choice: {
                        value: choice
                    }
                }
            }
        });
    };

    const addFieldChoicesAnswer = (fieldId: string, choices: string[]) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.CHOICES,
                    choices: {
                        values: choices
                    }
                }
            }
        });
    };

    const addOtherChoiceAnswer = (fieldId: string, other: string) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse?.answers || {}),
                [fieldId]: {
                    type: AnswerType.CHOICE,
                    choice: {
                        other
                    }
                }
            }
        });
    };

    const addOtherChoicesAnswer = (fieldId: string, other: string) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse?.answers || {}),
                [fieldId]: {
                    type: AnswerType.CHOICES,
                    choices: {
                        ...(formResponse?.answers ? formResponse?.answers[fieldId]?.choices : {}),
                        other
                    }
                }
            }
        });
    };

    const addFieldNumberAnswer = (fieldId: string, number: number) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.NUMBER,
                    number: number
                }
            }
        });
    };

    const addFieldBooleanAnswer = (fieldId: string, value: boolean) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.BOOLEAN,
                    boolean: value
                }
            }
        });
    };

    const addFieldEmailAnswer = (fieldId: string, email: string) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.EMAIL,
                    email: email
                }
            }
        });
    };

    const addFieldDateAnswer = (fieldId: string, date: string) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.DATE,
                    date: date
                }
            }
        });
    };

    const addFieldURLAnswer = (fieldId: string, url: string) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.URL,
                    url: url
                }
            }
        });
    };

    const addFieldPhoneNumberAnswer = (fieldId: string, phoneNumber: string) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.PHONE_NUMBER,
                    phone_number: phoneNumber
                }
            }
        });
    };

    const addFieldFileAnswer = (fieldId: string, fileMetaData: FileMetadata) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.FILE_UPLOAD,
                    file_metadata: fileMetaData
                }
            }
        });
    };

    const addFieldRatingAnswer = (fieldId: string, number: number) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.RATING,
                    number: number
                }
            }
        });
    };

    const addFieldLinearRatingAnswer = (fieldId: string, number: number) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.LINEAR_RATING,
                    number: number
                }
            }
        });
    };

    const setInvalidFields = (invalidFields: Record<string, Array<Invalidations>>) => {
        setFormResponse({
            ...formResponse,
            invalidFields
        });
    };

    const removeAnswer = (fieldId: string) => {
        delete formResponse!.answers![fieldId];
        setFormResponse({ ...formResponse });
    };

    const resetFormResponseAnswer = () => {
        setFormResponse({
            formId: '',
            answers: {}
        });
    };

    return {
        formResponse,
        setFormResponse,
        addFieldTextAnswer,
        addFieldBooleanAnswer,
        addFieldChoiceAnswer,
        addFieldDateAnswer,
        addFieldEmailAnswer,
        addFieldNumberAnswer,
        addFieldPhoneNumberAnswer,
        addFieldURLAnswer,
        addFieldChoicesAnswer,
        addOtherChoiceAnswer,
        addOtherChoicesAnswer,
        addFieldFileAnswer,
        addFieldRatingAnswer,
        addFieldLinearRatingAnswer,
        removeAnswer,
        setInvalidFields,
        resetFormResponseAnswer
    };
};

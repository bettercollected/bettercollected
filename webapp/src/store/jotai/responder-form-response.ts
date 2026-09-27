
import { atom, useAtom } from 'jotai';
import { useMemo } from 'react';

import { FileMetadata } from '@app/models/types/field-types';
import { useGroupItemScope } from '@app/store/jotai/group-item-scope';
import { itemScopeAnswers, writeItemAnswers } from '@app/utils/repeating-groups';
import { Invalidations } from '@app/utils/vvalidation-utils';

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
    LINEAR_RATING = 'linear_rating',
    TABULAR_INPUT = 'tabular_input',
    GROUP = 'group'
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
            tabular_value?: string[][];
            // Repeating group: one answers map (child id → answer) per item.
            items?: Array<Record<string, any>>;
        };
    };
    invalidFields?: Record<string, Array<Invalidations | string>>;
    anonymize?: boolean;
}

const initialFormResponse: FormResponse = {
    formId: '',
    answers: {}
    // `anonymize` starts UNDEFINED (not false): identity sharing is opt-in
    // (Design-Language §5), so until the responder touches the checkbox, the
    // effective value is decided at submit time — anonymous when identity is
    // optional, attached when the form requires a verified identity.
};

const formResponseAtom = atom<FormResponse>(initialFormResponse);

type FormResponseUpdate = FormResponse | ((previous: FormResponse) => FormResponse);

export const useFormResponse = () => {
    const [rootFormResponse, setRootFormResponse] = useAtom(formResponseAtom);
    const itemScope = useGroupItemScope();

    // Inside a repeating-group item, the setters below read and write the
    // item's answers through a scoped view (see utils/repeating-groups.ts);
    // everywhere else they work on the form's answers directly.
    const scopedView = (response: FormResponse): FormResponse => (itemScope ? { ...response, answers: itemScopeAnswers(response.answers, itemScope) as FormResponse['answers'] } : response);
    const formResponse = useMemo(() => scopedView(rootFormResponse), [rootFormResponse, itemScope]);
    const setFormResponse = (update: FormResponseUpdate) => {
        if (!itemScope) {
            setRootFormResponse(update as any);
            return;
        }
        setRootFormResponse((previous) => {
            const next = typeof update === 'function' ? update(scopedView(previous)) : update;
            return { ...previous, ...next, answers: writeItemAnswers(previous.answers, itemScope, next.answers || {}) as FormResponse['answers'] };
        });
    };

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
                        ...formResponse.answers[fieldId]?.choices,
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

    const addFieldTabularAnswer = (fieldId: string, value: string[][]) => {
        setFormResponse({
            ...formResponse,
            answers: {
                ...(formResponse.answers || {}),
                [fieldId]: {
                    type: AnswerType.TABULAR_INPUT,
                    tabular_value: value
                }
            }
        });
    };

    const setInvalidFields = (invalidFields: Record<string, Array<Invalidations | string>>) => {
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
        addFieldTabularAnswer,
        removeAnswer,
        setInvalidFields,
        resetFormResponseAnswer
    };
};

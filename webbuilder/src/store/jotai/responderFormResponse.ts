import { set } from 'lodash';

import { atom, useAtom } from 'jotai';

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
    PAYMENT = 'payment'
}

export interface FormResponse {
    currentSlide: number;
    formId: string;
    answers?: {
        [fieldId: string]: {
            type: AnswerType;
            text?: string;
            number?: number;
            email?: string;
            date?: string;
            phoneNumber?: string;
            url?: string;
            choice?: string;
            choices?: string[];
            boolean?: boolean;
        };
    };
    consent?: Array<any>;
}

const initialFormResponse: FormResponse = {
    formId: '',
    currentSlide: -1
};

const formResponseAtom = atom<FormResponse>(initialFormResponse);

export const useFormResponse = () => {
    const [formResponse, setFormResponse] = useAtom(formResponseAtom);

    const nextSlide = () => {
        const nextSlideNumber = formResponse.currentSlide + 1;
        setFormResponse({
            ...formResponse,
            currentSlide: nextSlideNumber
        });
    };

    const previousSlide = () => {
        setFormResponse({
            ...formResponse,
            currentSlide: formResponse.currentSlide + 1
        });
    };

    const setCurrentSlideToThankyouPage = () => {
        setFormResponse({
            ...formResponse,
            currentSlide: -2
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
                    choice: choice
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
                    choices: choices
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
                    phoneNumber: phoneNumber
                }
            }
        });
    };

    const removeAnswer = (fieldId: string) => {
        delete formResponse!.answers![fieldId];
        setFormResponse({ ...formResponse });
    };
    return {
        formResponse,
        currentSlide: formResponse.currentSlide,
        nextSlide,
        previousSlide,
        setFormResponse,
        addFieldBooleanAnswer,
        addFieldChoiceAnswer,
        addFieldDateAnswer,
        addFieldEmailAnswer,
        addFieldNumberAnswer,
        addFieldPhoneNumberAnswer,
        addFieldURLAnswer,
        addFieldChoicesAnswer,
        setCurrentSlideToThankyouPage
    };
};

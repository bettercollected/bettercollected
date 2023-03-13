import { StandardFormDto, StandardFormResponseDto } from '@app/models/dtos/form';

export const standardResponseMock: StandardFormDto = {
    formId: '1HsoSajeOrNZhdddDwquVzwIHp1b9UHccZp8AiYFNslk',
    title: 'Contact information',
    fields: [
        {
            questionId: '778b574a',
            formId: '1HsoSajeOrNZhdddDwquVzwIHp1b9UHccZp8AiYFNslk',
            title: 'Name',
            description: '',
            type: {
                type: 'INPUT_FIELD'
            },
            required: true,
            isMediaContent: false,
            isGroupQuestion: false,
            answer: ['sireto tours']
        },
        {
            questionId: '3e555b2b',
            formId: '1HsoSajeOrNZhdddDwquVzwIHp1b9UHccZp8AiYFNslk',
            title: 'Email',
            description: '',
            type: {
                type: 'INPUT_FIELD'
            },
            required: true,
            isMediaContent: false,
            isGroupQuestion: false,
            answer: ['siretotours@gmail.com']
        },
        {
            questionId: '3f7b522a',
            formId: '1HsoSajeOrNZhdddDwquVzwIHp1b9UHccZp8AiYFNslk',
            title: 'Address',
            description: '',
            type: {
                paragraph: true
            },
            required: true,
            isMediaContent: false,
            isGroupQuestion: false,
            answer: ['lalitpur']
        },
        {
            questionId: '458e9ec2',
            formId: '1HsoSajeOrNZhdddDwquVzwIHp1b9UHccZp8AiYFNslk',
            title: 'Phone number',
            description: '',
            type: {
                type: 'INPUT_FIELD'
            },
            isMediaContent: false,
            isGroupQuestion: false,
            answer: ['123456']
        },
        {
            questionId: '320744c8',
            formId: '1HsoSajeOrNZhdddDwquVzwIHp1b9UHccZp8AiYFNslk',
            title: 'Comments',
            description: '',
            type: {
                paragraph: true
            },
            isMediaContent: false,
            isGroupQuestion: false,
            answer: ['comments']
        }
    ],
    responseId: 'ACYDBNhw8uoY6ulZRQMYZEfsW0LKjff-ferhUaAqKMLRtRV4w0_of9bcyn9QV-Wnzw',
    provider: 'google',
    dataOwnerIdentifier: '',
    responseCreatedAt: '2022-12-15T10:25:03.540Z',
    responseUpdatedAt: '2022-12-15T10:25:03.540831Z'
};

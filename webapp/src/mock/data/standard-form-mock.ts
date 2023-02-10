import { StandardFormDto } from '@app/models/dtos/form';

export const dashboardFormMock: StandardFormDto = {
    formId: '1HsoSajeOrNZhdddDwquVzwIHp1b9UHccZp8AiYFNslk',
    title: 'Contact information',
    settings: {
        pinned: false,
        customUrl: 'contact-form',
        private: false,
        responseDataOwnerField: '3e555b2b',
        embedUrl: 'https://docs.google.com/forms/d/e/1FAIpQLSfIZ_lfi9nIJiW1_KOZPHm2xgw1RHRMhUt0CLi8L_UQQis2SA/viewform',
        provider: 'google'
    },
    questions: [
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
            isGroupQuestion: false
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
            isGroupQuestion: false
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
            isGroupQuestion: false
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
            isGroupQuestion: false
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
            isGroupQuestion: false
        }
    ]
};

export const dashboardFormsArrayMock = [
    dashboardFormMock,
    {
        formId: '1lWq-fpqmuxt3iKuz7h_siwc9y_vGkpgnoNxXg0cZNXc',
        title: 'Event registration',
        description: 'Event Timing: January 4th-6th, 2016\nEvent Address: 123 Your Street Your City, ST 12345\nContact us at (123) 456-7890 or no_reply@example.com',
        settings: {
            pinned: false,
            customUrl: '1lWq-fpqmuxt3iKuz7h_siwc9y_vGkpgnoNxXg0cZNXc',
            private: true,
            responseDataOwnerField: '5cc44f1e',
            embedUrl: 'https://docs.google.com/forms/d/e/1FAIpQLScQSGmhAyDR8XlxyuCiKh_SN54IOikCDsVlNGLt76xcy46_oQ/viewform',
            provider: 'google'
        },
        questions: [
            {
                questionId: '7cb5071a',
                formId: '1lWq-fpqmuxt3iKuz7h_siwc9y_vGkpgnoNxXg0cZNXc',
                title: 'Name',
                description: '',
                type: {
                    type: 'INPUT_FIELD'
                },
                required: true,
                isMediaContent: false,
                isGroupQuestion: false
            },
            {
                questionId: '5cc44f1e',
                formId: '1lWq-fpqmuxt3iKuz7h_siwc9y_vGkpgnoNxXg0cZNXc',
                title: 'Email',
                description: '',
                type: {
                    type: 'INPUT_FIELD'
                },
                required: true,
                isMediaContent: false,
                isGroupQuestion: false
            },
            {
                questionId: '1c918e91',
                formId: '1lWq-fpqmuxt3iKuz7h_siwc9y_vGkpgnoNxXg0cZNXc',
                title: 'Organization',
                description: '',
                type: {
                    type: 'INPUT_FIELD'
                },
                required: true,
                isMediaContent: false,
                isGroupQuestion: false
            },
            {
                questionId: '68800c44',
                formId: '1lWq-fpqmuxt3iKuz7h_siwc9y_vGkpgnoNxXg0cZNXc',
                title: 'What days will you attend?',
                description: '',
                type: {
                    type: 'CHECKBOX',
                    options: [
                        {
                            value: 'Day 1'
                        },
                        {
                            value: 'Day 2'
                        },
                        {
                            value: 'Day 3'
                        }
                    ]
                },
                required: true,
                isMediaContent: false,
                isGroupQuestion: false
            },
            {
                questionId: '23122d3f',
                formId: '1lWq-fpqmuxt3iKuz7h_siwc9y_vGkpgnoNxXg0cZNXc',
                title: 'Dietary restrictions',
                description: '',
                type: {
                    type: 'RADIO',
                    options: [
                        {
                            value: 'None'
                        },
                        {
                            value: 'Vegetarian'
                        },
                        {
                            value: 'Vegan'
                        },
                        {
                            value: 'Kosher'
                        },
                        {
                            value: 'Gluten-free'
                        },
                        {
                            isOther: true
                        }
                    ]
                },
                required: true,
                isMediaContent: false,
                isGroupQuestion: false
            },
            {
                questionId: '7db6e751',
                formId: '1lWq-fpqmuxt3iKuz7h_siwc9y_vGkpgnoNxXg0cZNXc',
                title: 'I understand that I will have to pay $$ upon arrival',
                description: '',
                type: {
                    type: 'CHECKBOX',
                    options: [
                        {
                            value: 'Yes'
                        }
                    ]
                },
                required: true,
                isMediaContent: false,
                isGroupQuestion: false
            }
        ]
    },
    {
        formId: 'UJs4vZ7O',
        title: 'All Fields',
        settings: {
            pinned: false,
            customUrl: 'UJs4vZ7O',
            private: true,
            responseDataOwnerField: 'z6x3HSdq8viG',
            provider: 'typeform'
        }
    }
];

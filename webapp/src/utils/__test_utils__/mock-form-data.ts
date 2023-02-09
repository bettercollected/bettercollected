import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';

const formObject = (uuid?: string) => ({
    formId: uuid || uuidv4(),
    title: 'form_title',
    description: 'Description',
    createdTime: new Date(),
    modifiedTime: new Date(),
    settings: {
        pinned: false,
        roles: [],
        customUrl: 'JMsmiqkH',
        embedUrl: 'hello',
        private: true,
        responseDataOwnerField: '',
        provider: 'typeform'
    },
    questions: [
        {
            questionId: '6852VwIVRkuo',
            title: "Hello, what's your name?",
            type: {
                type: 'INPUT_FIELD'
            },
            required: false,
            attachment: {
                href: 'https://images.typeform.com/images/WMALzu59xbXQ',
                type: 'image',
                embed_provider: 'no_embed',
                properties: {
                    description: 'alt_text'
                }
            }
        },
        {
            questionId: 'OeZu68HmfzoH',
            title: '...',
            type: {
                type: 'RANKING',
                options: [
                    {
                        value: 'Avatar 2'
                    },
                    {
                        value: 'Wwe'
                    },
                    {
                        value: 'New one'
                    },
                    {
                        value: '3'
                    },
                    {
                        value: '4'
                    }
                ]
            },
            required: false
        },
        {
            questionId: 'TlAc45eb4fmB',
            title: 'Ratings for avatar 2?',
            type: {
                type: 'RATING',
                shape: 'thunderbolt',
                steps: 3
            },
            required: false
        },
        {
            questionId: '8qW3uvHh1Bpq',
            title: 'This is a form.',
            type: {
                type: 'INPUT_FIELD'
            },
            required: false
        }
    ]
});

export const formArray = [formObject(), formObject(), formObject()];

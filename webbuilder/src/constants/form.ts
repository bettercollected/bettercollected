import { v4 } from 'uuid';

import { FieldTypes, StandardForm } from '@app/models/dtos/form';

export const defaultForm: StandardForm = {
    formId: '',
    description: '',
    title: '',
    fields: [
        {
            id: v4(),
            index: 0,
            type: FieldTypes.SLIDE,
            properties: {
                fields: [
                    {
                        id: v4(),
                        index: 0,
                        type: FieldTypes.SHORT_TEXT,
                        value: 'Hi, what is your name?',
                        properties: {
                            placeholder: 'Your full name please'
                        }
                    }
                ]
            }
        }
    ],
    theme: {
        title: 'Default',
        primary: '#2E2E2E',
        secondary: '#0764EB',
        tertiary: '#A2C5F8',
        accent: '#F2F7FF'
    }
};

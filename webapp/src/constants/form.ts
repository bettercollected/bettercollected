import { v4 } from 'uuid';

import { FieldTypes, StandardFormDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';

export const defaultForm: StandardFormDto = {
    formId: '',
    description: '',
    title: '',
    fields: [
        {
            id: v4(),
            index: 0,
            type: FieldTypes.SLIDE,
            properties: {
                layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND,
                fields: [
                    {
                        id: v4(),
                        index: 0,
                        type: FieldTypes.SHORT_TEXT,
                        title: 'Enter Question'
                    }
                ]
            }
        }
    ],
    welcomePage: {
        title: '',
        layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND
    },
    thankyouPage: [
        {
            layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND
        }
    ],
    theme: {
        title: 'Default',
        primary: '#101826',
        secondary: '#2456CC',
        tertiary: '#CBD5E6',
        accent: '#F6F8FC'
    }
};

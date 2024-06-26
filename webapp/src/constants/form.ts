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
                layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT,
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
        layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
    },
    thankyouPage: [
        {
            layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
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

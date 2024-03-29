import { v4 } from 'uuid';

import { FieldTypes } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import StandardForm from '@app/store/jotai/fetchedForm';

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
                layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT,
                fields: []
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
        primary: '#2E2E2E',
        secondary: '#0764EB',
        tertiary: '#A2C5F8',
        accent: '#F2F7FF'
    }
};

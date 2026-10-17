import { v4 } from 'uuid';

import { newFormTheme } from '@app/constants/theme';
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
                        type: FieldTypes.SHORT_TEXT
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
    // New forms start with Leaflet (constants/theme.ts NEW_FORM_THEME_TITLE).
    theme: newFormTheme()
};

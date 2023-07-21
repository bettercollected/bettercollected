import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

import { IBuilderTitleAndDescriptionObj } from './types';

export const builderTitleAndDescriptionList: Array<IBuilderTitleAndDescriptionObj> = [
    {
        id: 'field-title',
        tagName: 'h1',
        type: FormBuilderTagNames.LAYOUT_HEADER1,
        key: 'title',
        position: -2,
        placeholder: 'Form title',
        className: 'font-semibold text-3xl text-black-800'
    },
    {
        id: 'field-description',
        tagName: 'p',
        type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
        key: 'description',
        position: -1,
        placeholder: 'Form description',
        className: 'text-base text-black-800 min-h-[40px]'
    }
];

export function getInitialPropertiesForFieldType(type: FormBuilderTagNames) {
    switch (type) {
        case FormBuilderTagNames.INPUT_RATING:
            return {
                steps: 5
            };
        case FormBuilderTagNames.INPUT_CHECKBOXES:
        case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
        case FormBuilderTagNames.INPUT_RANKING:
        case FormBuilderTagNames.INPUT_DROPDOWN:
        case FormBuilderTagNames.INPUT_MULTISELECT:
            const choiceId = uuidv4();
            const properties: any = {
                choices: {
                    [choiceId]: {
                        id: choiceId,
                        value: ''
                    }
                }
            };
            if (type === FormBuilderTagNames.INPUT_CHECKBOXES || type === FormBuilderTagNames.INPUT_MULTISELECT) {
                properties['allowMultipleSelection'] = true;
            }
            return properties;
        default:
            return null;
    }
}

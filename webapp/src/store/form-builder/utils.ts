import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

import { Comparison, IBuilderTitleAndDescriptionObj, IFormFieldProperties, LogicalOperator } from './types';

export const builderTitleAndDescriptionList: Array<IBuilderTitleAndDescriptionObj> = [
    {
        id: 'item-form-title',
        tagName: 'h1',
        type: FormBuilderTagNames.LAYOUT_HEADER1,
        key: 'title',
        position: -2,
        placeholder: 'FORM_TITLE.PLACEHOLDER',
        className: 'font-bold text-[32px] text-black-800'
    },
    {
        id: 'item-form-description',
        tagName: 'p',
        type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
        key: 'description',
        position: -1,
        placeholder: 'FORM_DESCRIPTION.PLACEHOLDER',
        className: 'text-[16px] font-normal text-black-700 '
    }
];

export function getInitialPropertiesForFieldType(type: FormBuilderTagNames) {
    switch (type) {
        case FormBuilderTagNames.CONDITIONAL:
            const conditionalId = uuidv4();
            const actionId = uuidv4();
            return {
                conditions: {
                    [conditionalId]: {
                        id: conditionalId,
                        position: 0
                    }
                },
                actions: {
                    [actionId]: {
                        position: 0,
                        id: actionId,
                        payload: []
                    }
                },
                logicalOperator: LogicalOperator.AND
            };
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
            const properties: IFormFieldProperties = {
                activeChoiceId: choiceId,
                activeChoiceIndex: 0,
                choices: {
                    [choiceId]: {
                        id: choiceId,
                        value: '',
                        position: 0
                    }
                }
            };
            if (type === FormBuilderTagNames.INPUT_CHECKBOXES || type === FormBuilderTagNames.INPUT_MULTISELECT) {
                properties['allowMultipleSelection'] = true;
            }
            return properties;
    }
}

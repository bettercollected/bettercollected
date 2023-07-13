import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

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

import { FormField } from '@app/models/dtos/form';

export function validateSlide(slide: FormField, answers: Record<string, any>) {
    const invalidFields: Record<string, Array<Invalidations>> = {};
    slide?.properties?.fields?.forEach((field) => {
        if (field?.validations?.required && !answers[field.id]) {
            invalidFields[field.id] = [Invalidations.REQUIRED];
        }
    });
    return invalidFields;
}

export enum Invalidations {
    REQUIRED
}

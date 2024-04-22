import { FieldTypes } from '@app/models/dtos/form';

export function getPlaceholderValueForField(fieldType?: FieldTypes) {
    switch (fieldType) {
        case FieldTypes.EMAIL:
            return 'name@gmail.com';
        case FieldTypes.NUMBER:
            return '123';
        case FieldTypes.SHORT_TEXT:
            return 'Answer';
        case FieldTypes.LINK:
            return 'https://';
        case FieldTypes.PHONE_NUMBER:
            return '0123456789';
        default:
            return 'No Field Selected';
    }
}

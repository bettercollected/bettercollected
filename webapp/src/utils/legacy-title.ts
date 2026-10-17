import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

const CHOICE_TYPES: ReadonlyArray<string> = [FieldTypes.MULTIPLE_CHOICE, FieldTypes.DROP_DOWN, FieldTypes.RANKING, FieldTypes.YES_NO];

/**
 * The plain-text title of a field from before rich titles: its `value`, when
 * it has no `title`. On a choice question a `value` that names one of its
 * options is a preset answer, not a title (publish-checks `hasPresetAnswer`).
 */
export function legacyTitleText(field: Pick<StandardFormFieldDto, 'title' | 'value' | 'type' | 'properties'>): string | undefined {
    if (field?.title || typeof field?.value !== 'string' || !field.value.trim()) return undefined;
    if (CHOICE_TYPES.includes(field.type)) {
        const value = field.value.trim().toLowerCase();
        const options = (field.properties?.choices ?? []).map((choice: any) => String(choice?.value || choice?.label || '').trim().toLowerCase());
        if (field.type === FieldTypes.YES_NO) options.push('yes', 'no');
        if (options.includes(value)) return undefined;
    }
    return field.value;
}

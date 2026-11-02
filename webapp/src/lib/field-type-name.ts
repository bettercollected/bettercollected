/** The `t` of `useTranslation('builder')`, kept loose so any namespace's function fits. */
type Translate = (key: string, options?: Record<string, unknown>) => string;

/**
 * A question type's name in the builder's language: the Insert menu's name
 * (`FIELD_TYPES.<type>.NAME`), with the English name as the fallback.
 */
export function fieldTypeName(t: Translate, type: string | null | undefined, fallback = ''): string {
    if (!type) return fallback;
    return t(`FIELD_TYPES.${type}.NAME`, { defaultValue: fallback || type.replaceAll('_', ' ').toLowerCase() });
}

/**
 * The short name on a question's chip in the inspector and outline (a few differ from the Insert menu's:
 * "Text", "Calendar", "Upload"), falling back to the menu's name.
 */
export function fieldTypeChip(t: Translate, type: string | null | undefined, fallback = ''): string {
    if (!type) return fallback;
    return t(`FIELD_TYPES.${type}.CHIP`, { defaultValue: fieldTypeName(t, type, fallback) });
}

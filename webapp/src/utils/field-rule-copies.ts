import { StandardFormFieldDto } from '@app/models/dtos/form';

/**
 * Field rules (`properties.rules`, kept and enforced by the server) are not
 * copied when a question or a page is duplicated: their ids must be unique in
 * the form, and their references point at the original's questions. The
 * builder has no rule editor yet, so a copy simply starts without rules.
 * Removes them from `field` and every question inside it, in place.
 */
export function dropFieldRules(field: StandardFormFieldDto | undefined): void {
    const pending: Array<StandardFormFieldDto | undefined> = [field];
    while (pending.length) {
        const current = pending.pop();
        const properties = current?.properties as ({ rules?: unknown } & StandardFormFieldDto['properties']) | undefined;
        if (!properties) continue;
        if ('rules' in properties) delete properties.rules;
        pending.push(...(properties.fields ?? []));
    }
}

/** A rule the server left out of a save: its question and its id. */
export interface DroppedRule {
    fieldId?: string | null;
    ruleId?: string | null;
}

/**
 * `fields` without the given rules (the ones a save dropped). Returns the
 * same array when none of them is there; otherwise new arrays and objects
 * along the changed paths only, and a question left without rules loses
 * its `rules` key (as `dropFieldRules` leaves it).
 */
export function withoutFieldRules<T extends StandardFormFieldDto>(fields: T[], dropped: DroppedRule[]): T[] {
    const gone = new Map<string, Set<string>>();
    dropped.forEach(({ fieldId, ruleId }) => {
        if (!fieldId || !ruleId) return;
        if (!gone.has(fieldId)) gone.set(fieldId, new Set());
        gone.get(fieldId)!.add(ruleId);
    });
    if (!gone.size) return fields;
    const visit = (list: T[]): T[] => {
        let changed = false;
        const next = list.map((field) => {
            const properties = field.properties as ({ rules?: Array<{ id?: string }> } & StandardFormFieldDto['properties']) | undefined;
            if (!properties) return field;
            let updated: any = properties;
            const ids = gone.get(field.id);
            if (ids && Array.isArray(properties.rules) && properties.rules.some((rule) => rule?.id && ids.has(rule.id))) {
                const kept = properties.rules.filter((rule) => !(rule?.id && ids.has(rule.id)));
                updated = { ...properties };
                if (kept.length) updated.rules = kept;
                else delete updated.rules;
            }
            if (Array.isArray(properties.fields)) {
                const children = visit(properties.fields as T[]);
                if (children !== properties.fields) updated = { ...updated, fields: children };
            }
            if (updated === properties) return field;
            changed = true;
            return { ...field, properties: updated };
        });
        return changed ? next : list;
    };
    return visit(fields);
}

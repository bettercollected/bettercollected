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

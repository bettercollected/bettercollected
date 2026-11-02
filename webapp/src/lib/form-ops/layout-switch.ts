/**
 * The switch for layout containers (backend `LAYOUT_CONTAINERS_ENABLED`,
 * services/layout_containers.py): while it is off, an op that leaves a
 * container new or changed against the form the batch started from is
 * refused. A container may lose questions or be removed. What a form already
 * holds keeps working.
 *
 * Pass `layoutContainers: false` in the apply options to apply the switch (the
 * webapp learns it from the workspace permissions). The server checks every
 * save either way.
 */
import type { LayoutContainer } from '@app/models/dtos/form';
import { containersOf, memberLists } from '@app/utils/layout-containers';

import { pagesOf } from './model';
import type { FormDoc } from './types';

/** Ops that can leave a container new or changed (backend LAYOUT_OPS). */
export const LAYOUT_OPS = new Set<string>(['set_page_containers', 'add_field', 'add_group', 'insert_field', 'move_field', 'replace_field', 'add_page', 'insert_page', 'duplicate_page', 'splice_fields']);

export const LAYOUT_CONTAINERS_DISABLED_MESSAGE =
    'Layout containers (panels, tabs and field sets) cannot be added or changed on this server yet (LAYOUT_CONTAINERS_ENABLED is off). Containers that a form already has are kept, and may lose questions or be removed.';

/** `{container id: [shape, members of each tab]}`: the shape is everything but the members. */
export type LayoutSignatures = Map<string, [string, Array<Set<string>>]>;

const shape = (container: LayoutContainer): string => {
    const { fields: _fields, tabs, ...rest } = container;
    return JSON.stringify(sortKeys({ ...rest, ...(tabs ? { tabs: tabs.map(({ fields: _f, ...tab }) => tab) } : {}) }));
};

function sortKeys(value: any): any {
    if (Array.isArray(value)) return value.map(sortKeys);
    if (value && typeof value === 'object') {
        const out: Record<string, any> = {};
        for (const key of Object.keys(value).sort()) if (value[key] !== null && value[key] !== undefined) out[key] = sortKeys(value[key]);
        return out;
    }
    return value;
}

export function layoutSignatures(doc: FormDoc): LayoutSignatures {
    const found: LayoutSignatures = new Map();
    for (const page of pagesOf(doc)) for (const container of containersOf(page)) found.set(container.id, [shape(container), memberLists(container).map((list) => new Set(list))]);
    return found;
}

/** Ids of the containers of `doc` that `stored` does not have as they are, or with fewer questions. */
export function newOrChangedContainers(doc: FormDoc, stored: LayoutSignatures): string[] {
    const changed: string[] = [];
    for (const page of pagesOf(doc)) {
        for (const container of containersOf(page)) {
            const before = stored.get(container.id);
            if (!before) {
                changed.push(container.id);
                continue;
            }
            const now = memberLists(container).map((list) => new Set(list));
            if (shape(container) !== before[0] || now.length !== before[1].length || now.some((mine, i) => [...mine].some((id) => !before[1][i].has(id)))) changed.push(container.id);
        }
    }
    return changed;
}

/** The refusal an op earns when it left `doc` with a container new or changed against `stored`, or null. */
export function layoutProblem(doc: FormDoc, stored: LayoutSignatures, opName: string): string | null {
    if (!LAYOUT_OPS.has(opName)) return null;
    return newOrChangedContainers(doc, stored).length ? LAYOUT_CONTAINERS_DISABLED_MESSAGE : null;
}

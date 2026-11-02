/** Layout containers: the op that sets a page's containers, and the joins other ops make by position. */
import type { LayoutContainer, LayoutTab } from '@app/models/dtos/form';
import { CONTAINERS_MAX, CONTAINER_CONDITIONS_MAX, CONTAINER_ID_PREFIX, TAB_ID_PREFIX, containerProblems, formItemIds, freshId, stripTitle, titleProblem, usedIds } from '@app/utils/layout-containers';
import { CONTAINER_MEMBERS_MAX, CONTAINER_TITLE_MAX, LAYOUT_ID_PATTERN, LAYOUT_MEMBER_ID_MAX, TABS_MAX } from '@app/utils/layout-containers';

import { OpError, childrenOf, findPage, pagesOf } from '../model';
import type { SetPageContainersOp } from '../types';
import { type Handler, ensureProperties, setKey } from './context';
import { validatedConditions } from './fields';

/** pydantic's message for a payload shape the backend refuses on parsing. */
export function shapeProblem(spec: SetPageContainersOp['containers'] extends Array<infer T> | null | undefined ? T : never): string | null {
    if (!['panel', 'fieldset', 'tabs'].includes(spec.type)) return "Input should be 'panel', 'fieldset' or 'tabs'";
    for (const id of [spec.id, ...(spec.tabs ?? []).map((tab) => tab.id)]) if (id != null && !LAYOUT_ID_PATTERN.test(id)) return `String should match pattern '${LAYOUT_ID_PATTERN.source}'`;
    if (spec.title != null && [...spec.title].length > CONTAINER_TITLE_MAX) return `String should have at most ${CONTAINER_TITLE_MAX} characters`;
    // a tab's title is 1 to CONTAINER_TITLE_MAX characters (the backend's ContainerTabSpec); blank text is plainTitle's
    for (const tab of spec.tabs ?? []) {
        const length = [...String(tab.title ?? '')].length;
        if (length < 1) return 'String should have at least 1 character';
        if (length > CONTAINER_TITLE_MAX) return `String should have at most ${CONTAINER_TITLE_MAX} characters`;
    }
    if ([...(spec.fields ?? []), ...(spec.tabs ?? []).flatMap((tab) => tab.fields ?? [])].some((id) => [...String(id)].length > LAYOUT_MEMBER_ID_MAX)) return `String should have at most ${LAYOUT_MEMBER_ID_MAX} characters`;
    if ((spec.fields?.length ?? 0) > CONTAINER_MEMBERS_MAX || (spec.tabs ?? []).some((tab) => (tab.fields?.length ?? 0) > CONTAINER_MEMBERS_MAX)) return `List should have at most ${CONTAINER_MEMBERS_MAX} items after validation`;
    if ((spec.tabs?.length ?? 0) > TABS_MAX) return `List should have at most ${TABS_MAX} items after validation`;
    return null;
}

const TITLE_MESSAGES = { blank: 'A title cannot be empty.', format: 'A title cannot contain control characters.' };

const plainTitle = (value: string): string => {
    const problem = titleProblem(value);
    if (problem) throw new OpError(TITLE_MESSAGES[problem]);
    return stripTitle(value);
};

/** The stored container for a spec (the backend's LayoutContainer validation, message for message). */
export function buildContainer(spec: any, reserved: Set<string>, logic: LayoutContainer['logic'] | undefined): LayoutContainer {
    const tabs: LayoutTab[] = (spec.tabs ?? []).map((tab: any) => ({ id: tab.id || freshId(TAB_ID_PREFIX, reserved), title: plainTitle(String(tab.title ?? '')), fields: [...(tab.fields ?? [])] }));
    const id = spec.id || freshId(CONTAINER_ID_PREFIX, reserved);
    if (spec.type === 'tabs') {
        if (spec.fields != null || spec.title != null || spec.collapsed != null) throw new OpError('A tabs container has tabs only: no title, collapsed flag or fields of its own.');
        if (!tabs.length) throw new OpError('A tabs container needs at least one tab.');
        if (new Set(tabs.map((t) => t.id)).size !== tabs.length) throw new OpError('The tabs of a container need unique ids.');
        return { id, type: 'tabs', ...(logic ? { logic } : {}), tabs };
    }
    if (tabs.length) throw new OpError('Only a tabs container has tabs.');
    if (spec.title == null) throw new OpError(`A ${spec.type} needs a title.`);
    const title = plainTitle(spec.title);
    if (spec.type === 'fieldset' && spec.collapsed != null) throw new OpError('A field set cannot be collapsed.');
    if (!(spec.fields?.length ?? 0)) throw new OpError(`A ${spec.type} needs at least one question.`);
    return { id, type: spec.type, title, ...(spec.collapsed != null ? { collapsed: spec.collapsed } : {}), ...(logic ? { logic } : {}), fields: [...spec.fields] };
}

export const setPageContainers: Handler<SetPageContainersOp> = (ctx, op) => {
    const { page, pos } = findPage(ctx.state, op.pageId);
    const properties = ensureProperties(ctx.draft.fields![pos], false);
    if (!op.containers?.length) {
        setKey(properties, 'containers', undefined);
        return `Removed the layout containers on page '${op.pageId}'`;
    }
    if (op.containers.length > CONTAINERS_MAX) throw new OpError(`List should have at most ${CONTAINERS_MAX} items after validation, not ${op.containers.length}`);
    for (const spec of op.containers) {
        const problem = shapeProblem(spec);
        if (problem) throw new OpError(problem);
    }
    // ids on the other pages, and the questions of the pages before this one
    const others = pagesOf(ctx.state).filter((p) => p !== page);
    const taken = usedIds(others);
    const earlier = new Set<string>();
    for (const other of pagesOf(ctx.state)) {
        if (other === page) break;
        for (const field of childrenOf(other)) {
            earlier.add(field.id);
            for (const child of childrenOf(field)) earlier.add(child.id);
        }
    }
    const explicit = [...op.containers.map((spec) => spec.id), ...op.containers.flatMap((spec) => (spec.tabs ?? []).map((tab) => tab.id))].filter((id): id is string => !!id);
    if (new Set(explicit).size !== explicit.length || explicit.some((id) => taken.has(id))) throw new OpError('Container and tab ids must be unique in the form.');
    // a container or tab id is never the id of a page, question or group child
    const items = formItemIds(pagesOf(ctx.state));
    for (const id of explicit) if (items.has(id)) throw new OpError(`The id '${id}' is also the id of a question or page.`);
    for (const spec of op.containers) if ((spec.logic?.conditions?.length ?? 0) > CONTAINER_CONDITIONS_MAX) throw new OpError(`A container's rule can have at most ${CONTAINER_CONDITIONS_MAX} conditions.`);
    const reserved = new Set([...taken, ...explicit, ...items]);
    const built: LayoutContainer[] = op.containers.map((spec) => {
        const logic = spec.logic ? ({ action: spec.logic.action, operator: spec.logic.operator ?? 'AND', conditions: validatedConditions(ctx.state, spec.logic.conditions) } as any) : undefined;
        return buildContainer(spec, reserved, logic);
    });
    const problems = containerProblems({ ...page, properties: { ...page.properties, containers: built } }, new Set(taken), earlier, items);
    if (problems.length) throw new OpError(problems[0][1]);
    properties.containers = built as any;
    return `Set ${built.length} layout container(s) on page '${op.pageId}' (${built.map((c) => c.type).join(', ')})`;
};

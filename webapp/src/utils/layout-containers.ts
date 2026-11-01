/**
 * Layout containers of a page: structure checks, repair and membership.
 *
 * Twin of `common/common/layout_containers.py` (the shared cases are in
 * `docs/spec/layout-containers.cases.json`, run on both sides). A page's
 * `properties.containers` groups questions into a panel, a field set or a
 * strip of tabs. It is layout only: the page's flat question list is what
 * answers, logic, rules and exports read. What holds the model together:
 *
 * - members are top-level questions of the page (never a repeating group's
 *   children, never an internal "for office use" question), each in at most
 *   one container;
 * - the members of a container (tabs in strip order, then each tab's members)
 *   appear in the page in that order with no respondent-facing question
 *   between them, so the display order is the page order;
 * - container and tab ids are unique across the form.
 *
 * The functions here never change what they are given: they return the new
 * list of containers (or the same list when nothing changed).
 */
import type { LayoutContainer, LayoutTab, StandardFormFieldDto } from '@app/models/dtos/form';

export const CONTAINER_ID_PREFIX = 'c';
export const TAB_ID_PREFIX = 't';
export const LAYOUT_ID_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;
export const CONTAINERS_MAX = 20;
export const CONTAINER_MEMBERS_MAX = 100;
export const TABS_MAX = 8;
export const CONTAINER_TITLE_MAX = 120;

type Page = Pick<StandardFormFieldDto, 'id' | 'type' | 'properties'>;

/** The questions of a page, in order. */
export const pageFieldsOf = (page: Page | undefined | null): StandardFormFieldDto[] => (page?.properties?.fields as StandardFormFieldDto[] | undefined) ?? [];

export const containersOf = (page: Page | undefined | null): LayoutContainer[] => (page?.properties?.containers as LayoutContainer[] | undefined) ?? [];

/** Ids of the page's questions in order, internal ones left out (respondents never see them). */
export const respondentIds = (page: Page | undefined | null): string[] =>
    pageFieldsOf(page)
        .filter((field) => !field.internal)
        .map((field) => field.id);

/** The member lists of a container: one per tab (a panel or field set has its one list). */
export function memberLists(container: LayoutContainer): string[][] {
    if (container.type === 'tabs') return (container.tabs ?? []).map((tab) => tab.fields ?? []);
    return [container.fields ?? []];
}

/** A container's member ids in strip order. */
export const membersOf = (container: LayoutContainer): string[] => memberLists(container).flat();

/** The tabs of a tabs container; a panel or field set is one pseudo tab holding its members. */
export const tabsOf = (container: LayoutContainer): Array<LayoutTab | LayoutContainer> => (container.type === 'tabs' ? (container.tabs ?? []) : [container]);

/** `container` with its member lists replaced (`lists` as `memberLists` gives them). */
function withMembers(container: LayoutContainer, lists: string[][]): LayoutContainer {
    if (container.type === 'tabs') return { ...container, tabs: (container.tabs ?? []).map((tab, i) => ({ ...tab, fields: lists[i] })) };
    return { ...container, fields: lists[0] };
}

/** The container a question is in, or undefined. */
export const containerOfField = (page: Page | undefined | null, fieldId: string): LayoutContainer | undefined => containersOf(page).find((container) => membersOf(container).includes(fieldId));

/** The tab id a question is in (tabs only). */
export const tabOfField = (container: LayoutContainer, fieldId: string): string | undefined => container.tabs?.find((tab) => (tab.fields ?? []).includes(fieldId))?.id;

/** Every container and tab id of a form's pages. */
export function usedIds(pages: Array<Page | undefined | null>): Set<string> {
    const ids = new Set<string>();
    for (const page of pages) {
        for (const container of containersOf(page)) {
            ids.add(container.id);
            for (const tab of container.tabs ?? []) ids.add(tab.id);
        }
    }
    return ids;
}

/** The smallest unused `<prefix><n>` (n from 1); adds it to `taken`. Deterministic, so the server's and this engine agree. */
export function freshId(prefix: string, taken: Set<string>): string {
    let number = 1;
    while (taken.has(`${prefix}${number}`)) number++;
    taken.add(`${prefix}${number}`);
    return `${prefix}${number}`;
}

const sameLists = (a: string[][], b: string[][]) => a.length === b.length && a.every((list, i) => list.length === b[i].length && list.every((id, j) => id === b[i][j]));

/** Insert `fid` into `container` where its page position says: in the tab of the nearest member before it, after that member. */
function joinInto(container: LayoutContainer, fid: string, order: Map<string, number>): LayoutContainer {
    const here = order.get(fid) ?? 0;
    const lists = memberLists(container).map((list) => [...list]);
    let bestList = -1;
    let bestPos = -1;
    let bestMember = '';
    lists.forEach((list, tab) => {
        for (const member of list) {
            const pos = order.get(member) ?? -1;
            if (pos < here && pos > bestPos) {
                bestList = tab;
                bestPos = pos;
                bestMember = member;
            }
        }
    });
    if (bestList < 0) lists[0].unshift(fid);
    else lists[bestList].splice(lists[bestList].indexOf(bestMember) + 1, 0, fid);
    return withMembers(container, lists);
}

/** Questions inside a page's repeating groups (a container cannot hold them). */
function groupChildIds(page: Page): Set<string> {
    const ids = new Set<string>();
    for (const field of pageFieldsOf(page)) for (const child of (field.properties?.fields as StandardFormFieldDto[] | undefined) ?? []) ids.add(child.id);
    return ids;
}

/**
 * The page's containers made valid again where that can be done without
 * guessing; `changed` counts the things that changed. Drops members that no
 * longer exist on the page, are internal or repeated; drops a panel or field
 * set left without questions and a strip left without any; a container whose
 * members no longer follow the page's order is dissolved; questions left
 * between a container's members join it (the tab of the member before them).
 * Never adds a container.
 */
export function repairContainers(page: Page | undefined | null): { containers: LayoutContainer[] | undefined; changed: number } {
    const given = containersOf(page);
    if (!given.length) return { containers: page?.properties?.containers as LayoutContainer[] | undefined, changed: 0 };
    let changed = 0;
    const byId = new Map(pageFieldsOf(page).map((field) => [field.id, field]));
    const seen = new Set<string>();
    let kept: LayoutContainer[] = [];
    for (const container of given) {
        const lists = memberLists(container).map((list) =>
            list.filter((member) => {
                const field = byId.get(member);
                if (!field || field.internal || seen.has(member)) {
                    changed++;
                    return false;
                }
                seen.add(member);
                return true;
            })
        );
        if (!lists.some((list) => list.length)) {
            changed++;
            continue;
        }
        kept.push(sameLists(lists, memberLists(container)) ? container : withMembers(container, lists));
    }
    const order = new Map(respondentIds(page).map((id, i) => [id, i]));
    kept = kept.filter((container) => {
        const positions = membersOf(container).map((id) => order.get(id));
        const ok = positions.every((p) => p !== undefined) && positions.every((p, i) => i === 0 || (positions[i - 1] as number) < (p as number));
        if (!ok) changed++;
        return ok;
    });
    // questions left between the members join the container
    for (let i = 0; i < kept.length; i++) {
        const members = membersOf(kept[i]);
        if (members.length < 2) continue;
        const ids = respondentIds(page);
        const first = order.get(members[0]) as number;
        const last = order.get(members[members.length - 1]) as number;
        const taken = new Set(members);
        for (const fid of ids.slice(first + 1, last)) {
            if (taken.has(fid)) continue;
            if (kept.some((other) => membersOf(other).includes(fid))) continue;
            kept[i] = joinInto(kept[i], fid, order);
            changed++;
        }
    }
    if (!changed && kept.length === given.length) return { containers: page?.properties?.containers as LayoutContainer[], changed: 0 };
    return { containers: kept.length ? kept : undefined, changed };
}

/**
 * After the question `fid` was added to the page or moved on it (the page's
 * `fields` already show it there): it belongs to the container it sits strictly
 * inside of (a member of that container before it and one after it), and to no
 * other. A question that was the only member of its container stays in it
 * wherever it went (the container follows it), unless it landed inside another
 * one. At the edge of a run it is outside.
 */
export function joinByPosition(page: Page, fid: string): LayoutContainer[] | undefined {
    const given = containersOf(page);
    if (!given.length) return page.properties?.containers as LayoutContainer[] | undefined;
    const field = pageFieldsOf(page).find((f) => f.id === fid);
    if (!field) return repairContainers(page).containers;
    let sole = given.some((c) => {
        const members = membersOf(c);
        return members.length === 1 && members[0] === fid;
    });
    if (sole) {
        const order = new Map(respondentIds(page).map((id, i) => [id, i]));
        const here = order.get(fid) ?? -1;
        for (const container of given) {
            const members = membersOf(container);
            if (!(members.length === 1 && members[0] === fid) && members.length >= 2 && (order.get(members[0]) ?? here) < here && here < (order.get(members[members.length - 1]) ?? here)) sole = false;
        }
    }
    const without = sole
        ? given
        : given.map((container) =>
              withMembers(
                  container,
                  memberLists(container).map((list) => list.filter((id) => id !== fid))
              )
          );
    return repairContainers({ ...page, properties: { ...page.properties, containers: without } }).containers;
}

export interface LayoutProblem {
    pageId: string;
    containerId: string | null;
    message: string;
}

/**
 * Why the page's containers cannot stand: members that are unknown, internal,
 * a group's children or in two containers; members not next to each other or
 * out of page order; ids used twice (`taken` holds the ids of the pages
 * before, and is added to); rules that read a question that is not before the
 * container's first member, or one of its own. `earlier`: the ids of every
 * question on the earlier pages.
 */
export function containerProblems(page: Page, taken: Set<string> = new Set(), earlier: Set<string> = new Set()): Array<[string | null, string]> {
    const problems: Array<[string | null, string]> = [];
    const containers = containersOf(page);
    if (!containers.length) return problems;
    const fields = new Map(pageFieldsOf(page).map((f) => [f.id, f]));
    const children = groupChildIds(page);
    const order = new Map(respondentIds(page).map((id, i) => [id, i]));
    const claimed = new Map<string, string>();
    for (const container of containers) {
        const cid = container.id;
        const names = [cid, ...(container.type === 'tabs' ? (container.tabs ?? []).map((tab) => tab.id) : [])];
        for (const name of names) {
            if (taken.has(name)) problems.push([cid, `The id '${name}' is used more than once.`]);
            taken.add(name);
        }
        const members = membersOf(container);
        if (!members.length) {
            problems.push([cid, 'A container needs at least one question.']);
            continue;
        }
        if (new Set(members).size !== members.length) problems.push([cid, 'A question can be listed only once in a container.']);
        let bad = false;
        for (const member of members) {
            const owner = claimed.get(member);
            if (owner !== undefined && owner !== cid) {
                problems.push([cid, `The question '${member}' is already in the container '${owner}'.`]);
                bad = true;
            }
            claimed.set(member, cid);
            const field = fields.get(member);
            if (!field) {
                problems.push([cid, `The question '${member}' is not on this page` + (children.has(member) ? ' (it is inside a repeating group, which a container cannot split).' : '.')]);
                bad = true;
            } else if (field.internal) {
                problems.push([cid, `The internal question '${member}' cannot be in a container.`]);
                bad = true;
            }
        }
        if (bad) continue;
        const positions = members.map((m) => order.get(m) as number);
        if (!positions.every((p, i) => p === positions[0] + i)) {
            problems.push([cid, 'The questions of a container must be next to each other on the page, in the order of the container; move them first (move_field).']);
            continue;
        }
        for (const condition of container.logic?.conditions ?? []) {
            const source = condition.fieldId ?? '';
            if (!source) continue;
            if (members.includes(source)) problems.push([cid, "A container's rule cannot read one of its own questions."]);
            else if (order.has(source) && (order.get(source) as number) > positions[0]) problems.push([cid, "A container's rule can only read questions before the container."]);
            else if (!order.has(source) && !earlier.has(source)) problems.push([cid, `A container's rule reads the unknown question '${source}'.`]);
        }
    }
    return problems;
}

/** The container problems of a form's pages: `[page id, container id, message]` page by page, ids unique across the form. */
export function layoutProblems(pages: Page[]): LayoutProblem[] {
    const found: LayoutProblem[] = [];
    const taken = new Set<string>();
    const earlier = new Set<string>();
    for (const page of pages) {
        if (page.type !== 'slide') continue;
        for (const [containerId, message] of containerProblems(page, taken, earlier)) found.push({ pageId: page.id, containerId, message });
        for (const field of pageFieldsOf(page)) {
            earlier.add(field.id);
            for (const child of (field.properties?.fields as StandardFormFieldDto[] | undefined) ?? []) earlier.add(child.id);
        }
    }
    return found;
}

/** `{member id: [logic of each container it is in]}` for the logic that can hide (usable logic only). */
export function containerLogicIndex(pages: Array<Page | undefined | null> | undefined | null): Record<string, NonNullable<LayoutContainer['logic']>[]> {
    const index: Record<string, NonNullable<LayoutContainer['logic']>[]> = Object.create(null);
    for (const page of pages ?? []) {
        for (const container of containersOf(page)) {
            const logic = container.logic;
            if (!logic?.action || !(logic.conditions?.length ?? 0)) continue;
            for (const member of membersOf(container)) (index[member] ??= []).push(logic);
        }
    }
    return index;
}

/** Does any page hold a container? */
export const formHasContainers = (pages: Array<Page | undefined | null> | undefined | null): boolean => (pages ?? []).some((page) => containersOf(page).length > 0);

/** What a page shows in order: a plain question, or a container with its questions (in page order). */
export type PageBlock<T extends { id: string }> = { kind: 'field'; field: T } | { kind: 'container'; container: LayoutContainer; members: T[]; tabs?: Array<{ tab: LayoutTab; members: T[] }> };

/**
 * The page's `fields` (as shown now: hidden ones already left out) as blocks:
 * a container becomes one block at the place of its first visible member,
 * holding its visible members (and per tab for tabs). A container with
 * nothing visible is not a block.
 */
export function blocksOf<T extends { id: string }>(page: Page | undefined | null, visible: T[]): Array<PageBlock<T>> {
    const containers = containersOf(page);
    if (!containers.length) return visible.map((field) => ({ kind: 'field' as const, field }));
    const byId = new Map(visible.map((field) => [field.id, field]));
    const owner = new Map<string, LayoutContainer>();
    for (const container of containers) for (const member of membersOf(container)) owner.set(member, container);
    const placed = new Set<string>();
    const blocks: Array<PageBlock<T>> = [];
    for (const field of visible) {
        const container = owner.get(field.id);
        if (!container) {
            blocks.push({ kind: 'field', field });
            continue;
        }
        if (placed.has(container.id)) continue;
        placed.add(container.id);
        const list = (ids: string[]) => ids.map((id) => byId.get(id)).filter((f): f is T => !!f);
        if (container.type === 'tabs') {
            const tabs = (container.tabs ?? []).map((tab) => ({ tab, members: list(tab.fields ?? []) }));
            const members = tabs.flatMap((t) => t.members);
            if (members.length) blocks.push({ kind: 'container', container, members, tabs });
        } else {
            const members = list(container.fields ?? []);
            if (members.length) blocks.push({ kind: 'container', container, members });
        }
    }
    return blocks;
}

/** The id of the question an invalid-field key belongs to: the key itself, or the repeating group a scoped key (`<child id>::<index>`) is in. */
export function memberIdOfKey(page: Page | undefined | null, key: string): string | undefined {
    const fields = pageFieldsOf(page);
    if (fields.some((field) => field.id === key)) return key;
    const at = key.lastIndexOf('::');
    if (at <= 0) return undefined;
    const childId = key.slice(0, at);
    return fields.find((field) => ((field.properties?.fields as StandardFormFieldDto[] | undefined) ?? []).some((child) => child.id === childId))?.id;
}

/** The container (and its tab id, for tabs) that holds the question an invalid-field key belongs to. */
export function containerOfKey(page: Page | undefined | null, key: string): { container: LayoutContainer; tabId?: string } | undefined {
    const member = memberIdOfKey(page, key);
    if (!member) return undefined;
    const container = containerOfField(page, member);
    return container ? { container, tabId: tabOfField(container, member) } : undefined;
}

/**
 * Where the review page and the response views (which list the questions flat)
 * put a heading: for each of `fieldIds`, in order, the title of the container
 * (or, for tabs, the tab) that a run of them starts, `null` where a run of
 * questions outside any container starts after a headed one, and `undefined`
 * for the rest. So a panel's questions are introduced by its title, and a
 * question after it is not read as part of it.
 */
export function runHeadings(page: Page | undefined | null, fieldIds: string[]): Array<string | null | undefined> {
    let last = '';
    return fieldIds.map((id, position) => {
        const container = containerOfField(page, id);
        const key = container ? `${container.id}:${tabOfField(container, id) ?? ''}` : '';
        if (key === last) return undefined;
        last = key;
        if (!container) return position === 0 ? undefined : null;
        const tab = container.type === 'tabs' ? container.tabs?.find((t) => t.id === tabOfField(container, id)) : undefined;
        return (container.type === 'tabs' ? tab?.title : container.title) || undefined;
    });
}

/** What the builder's canvas draws for a page's question ids: a plain question, or the frame of a container with the ids it holds (in page order). */
export type CanvasBlock = { kind: 'field'; id: string } | { kind: 'container'; container: LayoutContainer; ids: string[] };

export function canvasBlocks(fieldIds: string[], containers: LayoutContainer[] | undefined | null): CanvasBlock[] {
    if (!containers?.length) return fieldIds.map((id) => ({ kind: 'field' as const, id }));
    const present = new Set(fieldIds);
    const owner = new Map<string, LayoutContainer>();
    for (const container of containers) for (const member of membersOf(container)) if (present.has(member)) owner.set(member, container);
    const placed = new Set<string>();
    const blocks: CanvasBlock[] = [];
    for (const id of fieldIds) {
        const container = owner.get(id);
        if (!container) blocks.push({ kind: 'field', id });
        else if (!placed.has(container.id)) {
            placed.add(container.id);
            blocks.push({ kind: 'container', container, ids: membersOf(container).filter((member) => present.has(member)) });
        }
    }
    return blocks;
}

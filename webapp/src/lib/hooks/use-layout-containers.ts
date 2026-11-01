'use client';

import { useStore } from 'jotai';
import { v4 } from 'uuid';

import type { ContainerSpec } from '@app/lib/form-ops/types';
import { FieldTypes, LayoutContainer, LayoutTab, StandardFormFieldDto } from '@app/models/dtos/form';
import { useBuilderActions } from '@app/store/jotai/field-selectors';
import { dispatchAtom, formDocAtom } from '@app/store/jotai/form-document';
import { CONTAINER_ID_PREFIX, TABS_MAX, TAB_ID_PREFIX, containersOf, freshId, membersOf, pageFieldsOf, respondentIds, usedIds } from '@app/utils/layout-containers';

export type ContainerKind = LayoutContainer['type'];

const first = (container: LayoutContainer) => membersOf(container)[0];

/** The containers in page order (the order the questions are in). */
function inPageOrder(page: StandardFormFieldDto, containers: LayoutContainer[]): LayoutContainer[] {
    const order = new Map(respondentIds(page).map((id, i) => [id, i]));
    return [...containers].sort((a, b) => (order.get(first(a)) ?? 0) - (order.get(first(b)) ?? 0));
}

/** The op's spec for a container (the stored shape is the spec's shape). */
const spec = (container: LayoutContainer): ContainerSpec => container as unknown as ContainerSpec;

export interface NewContainerNames {
    /** Title of a new panel or field set; the tabs' titles are `tab(n)`. */
    title: string;
    tab: (n: number) => string;
}

/**
 * What the builder does with layout containers, each as one undo step through
 * the ops engine (`set_page_containers`, `insert_field`, `move_field`): the
 * engine and the same checks the server runs decide what is accepted. Reads
 * the document when an edit is made, never subscribes to it.
 */
export function useLayoutContainerActions() {
    const store = useStore();
    const { getNewField } = useBuilderActions();
    const newQuestion = (fieldId: string, index: number) => ({ ...getNewField({ name: 'Short text', type: FieldTypes.SHORT_TEXT, icon: null }, fieldId, 0), index }) as StandardFormFieldDto;
    const doc = () => store.get(formDocAtom);
    const page = (pageId: string) => (doc().fields ?? []).find((p) => p?.id === pageId);
    const send = (ops: unknown[], label: string, coalesceKey?: string): boolean => store.set(dispatchAtom, { ops: ops as any, label, coalesceKey });

    /** Replace the page's containers with `change(its containers)`. */
    const change = (pageId: string, label: string, update: (containers: LayoutContainer[], taken: Set<string>) => LayoutContainer[], coalesceKey?: string): boolean => {
        const target = page(pageId);
        if (!target) return false;
        const taken = usedIds(doc().fields ?? []);
        const next = inPageOrder(target, update(containersOf(target), taken));
        return send([{ op: 'set_page_containers', pageId, containers: next.length ? next.map(spec) : null }], label, coalesceKey);
    };

    const newContainer = (kind: ContainerKind, members: string[], taken: Set<string>, names: NewContainerNames): LayoutContainer => {
        const id = freshId(CONTAINER_ID_PREFIX, taken);
        if (kind === 'tabs') {
            const tabs: LayoutTab[] = [1, 2].map((n) => ({ id: freshId(TAB_ID_PREFIX, taken), title: names.tab(n), fields: n === 1 ? members : [] }));
            return { id, type: 'tabs', tabs };
        }
        return { id, type: kind, title: names.title, fields: members };
    };

    return {
        /** Put the (adjacent, ungrouped) questions into a new container. */
        group(pageId: string, kind: ContainerKind, fieldIds: string[], names: NewContainerNames, label = 'Group questions') {
            return change(pageId, label, (containers, taken) => [...containers, newContainer(kind, fieldIds, taken, names)]);
        },

        /** A new container with a new short text question at `index` of the page (the insert menu). */
        insertNew(pageId: string, kind: ContainerKind, index: number, names: NewContainerNames, label = 'Add container'): string | null {
            const target = page(pageId);
            if (!target) return null;
            const fieldId = v4();
            const taken = usedIds(doc().fields ?? []);
            const field = newQuestion(fieldId, index);
            // the new question sits at an edge, so the container is set explicitly right after it
            const container = newContainer(kind, [fieldId], taken, names);
            const ok = send(
                [
                    { op: 'insert_field', pageId, index, field },
                    {
                        op: 'set_page_containers',
                        pageId,
                        containers: inPageOrder({ ...target, properties: { ...target.properties, fields: [...pageFieldsOf(target).slice(0, index), field, ...pageFieldsOf(target).slice(index)] } }, [...containersOf(target), container]).map(spec)
                    }
                ],
                label
            );
            return ok ? fieldId : null;
        },

        /** Take the container away (its questions stay where they are). */
        ungroup(pageId: string, containerId: string) {
            return change(pageId, 'Ungroup questions', (containers) => containers.filter((c) => c.id !== containerId));
        },

        /** Change one container (title typing coalesces into one undo step). */
        update(pageId: string, containerId: string, patch: Partial<LayoutContainer> | ((container: LayoutContainer) => LayoutContainer), label = 'Edit container', coalesceKey?: string) {
            return change(pageId, label, (containers) => containers.map((c) => (c.id === containerId ? (typeof patch === 'function' ? patch(c) : { ...c, ...patch }) : c)), coalesceKey);
        },

        /** Add a question at the end of a container (or of one of its tabs) and keep it a member. */
        addQuestion(pageId: string, containerId: string, tabId?: string): string | null {
            const target = page(pageId);
            const container = containersOf(target).find((c) => c.id === containerId);
            if (!target || !container) return null;
            const lists = container.type === 'tabs' ? (container.tabs ?? []).map((tab) => ({ id: tab.id, fields: tab.fields ?? [] })) : [{ id: undefined as string | undefined, fields: container.fields ?? [] }];
            const at = Math.max(
                0,
                lists.findIndex((list) => list.id === tabId)
            );
            // after the last question of this tab, or of the nearest tab before it that has one; at the container's start otherwise
            let anchor: string | undefined;
            for (let i = at; i >= 0 && !anchor; i--) anchor = lists[i].fields[lists[i].fields.length - 1];
            const all = pageFieldsOf(target);
            const index = anchor ? all.findIndex((f) => f.id === anchor) + 1 : all.findIndex((f) => f.id === membersOf(container)[0]);
            const fieldId = v4();
            const field = newQuestion(fieldId, index);
            const updated = containersOf(target).map((c) => {
                if (c.id !== containerId) return c;
                if (c.type === 'tabs') return { ...c, tabs: (c.tabs ?? []).map((tab, i) => (i === at ? { ...tab, fields: [...(tab.fields ?? []), fieldId] } : tab)) };
                return { ...c, fields: [...(c.fields ?? []), fieldId] };
            });
            // the question is placed after the tab's last one, then its place in the container is said explicitly (the edge of a run is outside by position)
            // the ids of the other tabs keep their order after the new one
            const ok = send(
                [
                    { op: 'insert_field', pageId, index, field },
                    { op: 'set_page_containers', pageId, containers: updated.map(spec) }
                ],
                'Add question'
            );
            return ok ? fieldId : null;
        },

        addTab(pageId: string, containerId: string, title: string) {
            return change(pageId, 'Add tab', (containers, taken) =>
                containers.map((c) => (c.id === containerId && c.type === 'tabs' && (c.tabs?.length ?? 0) < TABS_MAX ? { ...c, tabs: [...(c.tabs ?? []), { id: freshId(TAB_ID_PREFIX, taken), title, fields: [] }] } : c))
            );
        },

        /** Remove a tab; its questions stay on the page, in the tab before it (the first tab's go to the new first tab). */
        removeTab(pageId: string, containerId: string, tabId: string) {
            return change(pageId, 'Remove tab', (containers) =>
                containers.map((c) => {
                    const tabs = c.tabs ?? [];
                    const at = tabs.findIndex((tab) => tab.id === tabId);
                    if (c.id !== containerId || c.type !== 'tabs' || at < 0 || tabs.length < 2) return c;
                    const moved = tabs[at].fields ?? [];
                    const rest = tabs.filter((_, i) => i !== at);
                    const into = at > 0 ? at - 1 : 0;
                    rest[into] = { ...rest[into], fields: at > 0 ? [...(rest[into].fields ?? []), ...moved] : [...moved, ...(rest[into].fields ?? [])] };
                    return { ...c, tabs: rest };
                })
            );
        },

        /** Swap a tab with its neighbour; the questions swap places with it (they must stay in the order of the strip). */
        moveTab(pageId: string, containerId: string, tabId: string, direction: -1 | 1): boolean {
            const target = page(pageId);
            const container = containersOf(target).find((c) => c.id === containerId);
            if (!target || !container || container.type !== 'tabs') return false;
            const tabs = [...(container.tabs ?? [])];
            const at = tabs.findIndex((tab) => tab.id === tabId);
            const to = at + direction;
            if (at < 0 || to < 0 || to >= tabs.length) return false;
            // new strip order, and the page order that goes with it: the questions of the strip in that order, where the strip is now
            [tabs[at], tabs[to]] = [tabs[to], tabs[at]];
            const members = tabs.flatMap((tab) => tab.fields ?? []);
            const old = membersOf(container);
            const all = pageFieldsOf(target);
            const start = all.findIndex((f) => f.id === old[0]);
            const reordered = [...all.slice(0, start), ...members.map((id) => all.find((f) => f.id === id)!), ...all.slice(start + old.length)];
            const ops: unknown[] = [];
            // moves that put the strip's questions in their new order, then the strip itself
            const working = all.map((f) => f.id);
            reordered.forEach((field, position) => {
                const from = working.indexOf(field.id);
                if (from !== position) {
                    ops.push({ op: 'move_field', fieldId: field.id, index: position });
                    working.splice(from, 1);
                    working.splice(position, 0, field.id);
                }
            });
            ops.push({
                op: 'set_page_containers',
                pageId,
                containers: containersOf(target)
                    .map((c) => (c.id === containerId ? { ...c, tabs } : c))
                    .map(spec)
            });
            return send(ops, 'Move tab');
        },

        /** Take a question out of its container by moving it to just before the container (it is outside by position). */
        moveOut(pageId: string, fieldId: string): boolean {
            const target = page(pageId);
            const container = containersOf(target).find((c) => membersOf(c).includes(fieldId));
            if (!target || !container) return false;
            const members = membersOf(container);
            const before = pageFieldsOf(target).findIndex((f) => f.id === members[0]);
            // the first member steps up past the question before the container; with none, the container's questions come first
            const index = members[0] === fieldId ? (before > 0 ? before - 1 : members.length - 1) : before;
            return send([{ op: 'move_field', fieldId, index }], 'Move out of the container');
        }
    };
}

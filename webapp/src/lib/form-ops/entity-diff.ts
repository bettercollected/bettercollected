/**
 * `entityDiff(prev, next)`: the ops that turn one form document into another,
 * entity by entity — new pages and questions inserted whole (`insert_page`,
 * `insert_field`), moved ones moved, removed ones removed, changed ones
 * replaced (`replace_field`, `update_page`) and form-level keys updated. It
 * is how undo is built (see inverse.ts) and how a whole new document (an AI
 * proposal, a server copy) is taken in as ordinary ops.
 *
 * Unchanged pages keep their reference between the two documents (the
 * engine shares structure), so only the pages whose reference differs are
 * looked into.
 *
 * Not expressed: form-level keys no op sets (endings, actions, ...), and
 * clearing a title, description or theme entirely; such differences are
 * left as they are.
 */
import { childrenOf, clone, isRepeatingGroup, isSlide, jsonEqual, withoutNulls } from './model';
import type { FormDoc, FormField, FormOp, FormSettingsPatch, PagePatch, UpdateLogoOp } from './types';

// ---------------------------------------------------------------------------
// Form-level keys
// ---------------------------------------------------------------------------

/** Form key -> key of update_logo (the logo itself only changes by an upload). */
const LOGO_KEYS = { logoPosition: 'position', logoAlt: 'alt', useWorkspaceLogo: 'useWorkspaceLogo' } as const;
const WELCOME_KEYS = ['title', 'description', 'layout', 'imageUrl', 'buttonText'];
const PAGE_KEYS = ['layout', 'theme', 'position', 'showQuestionNumbers', 'sectionTitle'];
const SETTINGS_TEXT_KEYS = ['purpose', 'retentionText', 'privacyPolicyUrl'] as const;
const SETTINGS_SWITCH_KEYS = ['requireVerifiedIdentity', 'allowEditingResponse', 'showSubmissionNumber'] as const;

function formLevelOps(from: FormDoc, to: FormDoc): FormOp[] {
    const ops: FormOp[] = [];
    const titleChanged = from.title !== to.title && !jsonEqual(from.title, to.title);
    const descriptionChanged = from.description !== to.description && !jsonEqual(from.description, to.description);
    if (titleChanged || descriptionChanged) {
        ops.push({ op: 'update_form_info', ...(titleChanged ? { title: to.title ?? '' } : {}), ...(descriptionChanged ? { description: to.description ?? '' } : {}) });
    }
    // update_form_info also titles the welcome page
    const welcome = titleChanged && from.welcomePage != null ? { ...from.welcomePage, title: to.title ?? '' } : from.welcomePage;
    if (welcome !== to.welcomePage && !jsonEqual(welcome, to.welcomePage)) {
        const patch: Record<string, any> = {};
        for (const key of WELCOME_KEYS) {
            const wanted = (to.welcomePage as Record<string, any> | undefined)?.[key];
            if (!jsonEqual((welcome as Record<string, any> | undefined)?.[key], wanted)) patch[key] = wanted ?? null;
        }
        if (Object.keys(patch).length) ops.push({ op: 'update_welcome_page', patch });
    }
    if (from.theme !== to.theme && to.theme != null && !jsonEqual(from.theme, to.theme)) ops.push({ op: 'update_theme', theme: clone(to.theme) });
    if (from.hiddenFields !== to.hiddenFields && !jsonEqual(from.hiddenFields ?? [], to.hiddenFields ?? [])) ops.push({ op: 'set_hidden_fields', names: [...(to.hiddenFields ?? [])] });
    const logo: Record<string, any> = {};
    for (const [key, opKey] of Object.entries(LOGO_KEYS)) if (!jsonEqual((from as any)[key], (to as any)[key])) logo[opKey] = (to as any)[key] ?? null;
    if (Object.keys(logo).length) ops.push({ op: 'update_logo', ...logo } as UpdateLogoOp);
    if (from.settings !== to.settings) {
        const a = (from.settings ?? {}) as Record<string, any>;
        const b = (to.settings ?? {}) as Record<string, any>;
        const patch: FormSettingsPatch = {};
        for (const key of SETTINGS_TEXT_KEYS) if ((a[key] ?? '') !== (b[key] ?? '')) patch[key] = b[key] ?? '';
        for (const key of SETTINGS_SWITCH_KEYS) if ((a[key] ?? null) !== (b[key] ?? null)) patch[key] = !!b[key];
        if (Object.keys(patch).length) ops.push({ op: 'update_form_settings', patch });
    }
    return ops;
}

// ---------------------------------------------------------------------------
// Pages and questions
// ---------------------------------------------------------------------------

interface Entry {
    field: FormField;
    /** 'p:<page id>' or 'g:<group id>'. */
    container: string;
}

/** Questions of `pages` (repeating groups' questions included) and the order of each container. */
function indexPages(pages: FormField[]) {
    const fields = new Map<string, Entry>();
    const containers = new Map<string, string[]>();
    for (const page of pages) {
        const key = `p:${page.id}`;
        const ids: string[] = [];
        for (const field of childrenOf(page)) {
            ids.push(field.id);
            fields.set(field.id, { field, container: key });
            if (isRepeatingGroup(field)) {
                const groupKey = `g:${field.id}`;
                containers.set(
                    groupKey,
                    childrenOf(field).map((child) => {
                        fields.set(child.id, { field: child, container: groupKey });
                        return child.id;
                    })
                );
            }
        }
        containers.set(key, ids);
    }
    return { fields, containers };
}

/** Equal apart from `index` (and, with `skipChildren`, apart from the questions inside). */
function sameField(a: FormField, b: FormField, skipChildren: boolean): boolean {
    if (a === b) return true;
    const strip = (f: FormField) => {
        const { index: _index, ...rest } = f;
        if (skipChildren && rest.properties) {
            const { fields: _fields, ...properties } = rest.properties;
            return { ...rest, properties };
        }
        return rest;
    };
    return jsonEqual(strip(a), strip(b));
}

/** The ops that give page `a` the own settings of page `b` (`update_page`, `set_page_jumps`); other page keys are not expressed. */
function pageOps(a: FormField, b: FormField): FormOp[] {
    const pa = (a.properties ?? {}) as Record<string, any>;
    const pb = (b.properties ?? {}) as Record<string, any>;
    const patch: Record<string, any> = {};
    for (const key of PAGE_KEYS) if (pa[key] !== pb[key] && !jsonEqual(pa[key], pb[key])) patch[key] = pb[key] === undefined ? null : clone(pb[key]);
    if (!jsonEqual((a as any).imageUrl, (b as any).imageUrl)) patch.imageUrl = (b as any).imageUrl ?? null;
    const ops: FormOp[] = [];
    if (Object.keys(patch).length) ops.push({ op: 'update_page', pageId: b.id, patch: patch as PagePatch });
    if (pa.jumps !== pb.jumps && !jsonEqual(pa.jumps, pb.jumps)) {
        const jumps = (pb.jumps ?? []).map((jump: any) => ({
            operator: jump.operator,
            target: jump.target,
            conditions: (jump.conditions ?? []).map((c: any) => ({ fieldId: c.fieldId, comparison: c.comparison, value: c.value, groupMode: c.groupMode, childFieldId: c.childFieldId }))
        }));
        ops.push({ op: 'set_page_jumps', pageId: b.id, jumps: jumps.length ? withoutNulls(jumps) : null });
    }
    return ops;
}

/** Content ops only: replace the questions and update the pages that differ, structure being equal. */
function contentOps(fromPages: Map<string, FormField>, toPages: FormField[], from: ReturnType<typeof indexPages>, to: ReturnType<typeof indexPages>, forced: Set<string>): FormOp[] {
    const ops: FormOp[] = [];
    for (const page of toPages) {
        const before = fromPages.get(page.id);
        if (!before || before === page) continue;
        ops.push(...pageOps(before, page));
    }
    const replaced = new Set<string>();
    for (const [id, { field }] of to.fields) {
        const entry = to.fields.get(id)!;
        if (entry.container.startsWith('g:') && replaced.has(entry.container.slice(2))) continue;
        const before = from.fields.get(id)?.field;
        const differs = !!before && before !== field && !sameField(before, field, isRepeatingGroup(field) && isRepeatingGroup(before));
        if (differs || forced.has(id)) {
            ops.push({ op: 'replace_field', field: clone(field) });
            replaced.add(id);
        }
    }
    return ops;
}

function structureOps(from: FormDoc, to: FormDoc): FormOp[] {
    const fromAll = (from.fields ?? []).filter(isSlide);
    const toAll = (to.fields ?? []).filter(isSlide);
    const fromById = new Map(fromAll.map((p) => [p.id, p]));
    const toById = new Map(toAll.map((p) => [p.id, p]));
    const changedFrom = fromAll.filter((p) => toById.get(p.id) !== p);
    const changedTo = toAll.filter((p) => fromById.get(p.id) !== p);
    const fromIdx = indexPages(changedFrom);
    const toIdx = indexPages(changedTo);

    const ops: FormOp[] = [];
    // simulated layout while the ops are planned
    const containers = new Map([...fromIdx.containers].map(([key, ids]) => [key, [...ids]]));
    const where = new Map([...fromIdx.fields].map(([id, entry]) => [id, entry.container]));
    const pageOrder = fromAll.map((p) => p.id);
    const inserted = new Set<string>();
    const isNew = (id: string) => !fromIdx.fields.has(id) && !inserted.has(id);
    // questions to replace at the end, whatever they look like now
    const forced = new Set<string>();
    /**
     * A copy to insert, without date rules: a rule may use a question not
     * inserted yet, and the engine refuses that; the rules come with a
     * replace_field at the end.
     */
    const withoutRules = (field: FormField): FormField => {
        for (const item of [field, ...childrenOf(field)]) {
            if (item.properties?.dateRules) {
                delete item.properties.dateRules;
                forced.add(item.id);
            }
        }
        return field;
    };
    const scopeOf = (key: string | undefined) => (key?.startsWith('g:') ? key : 'page');
    /**
     * A move in or out of a repeating group drops the date rules across the
     * boundary (on the moved question and on those using it) until the
     * other questions are in place too: those questions are replaced at the
     * end.
     */
    const noteMove = (id: string, fromKey: string | undefined, toKey: string) => {
        if (scopeOf(fromKey) === scopeOf(toKey)) return;
        forced.add(id);
        for (const [otherId, { field }] of toIdx.fields) if (field.properties?.dateRules?.some((rule: any) => rule.fieldId === id)) forced.add(otherId);
    };
    const place = (id: string, key: string, index: number) => {
        const list = containers.get(key)!;
        list.splice(Math.max(0, Math.min(index, list.length)), 0, id);
        where.set(id, key);
    };
    const unplace = (id: string) => {
        const list = containers.get(where.get(id)!)!;
        list.splice(list.indexOf(id), 1);
        where.delete(id);
    };
    /** A new question as inserted: a group with only its new questions (the others are moved in). */
    const newField = (field: FormField): FormField => {
        const copy = clone(field);
        if (isRepeatingGroup(copy)) copy.properties!.fields = childrenOf(copy).filter((child) => isNew(child.id));
        return withoutRules(copy);
    };
    const noteInserted = (field: FormField, key: string) => {
        inserted.add(field.id);
        where.set(field.id, key);
        if (isRepeatingGroup(field)) {
            const groupKey = `g:${field.id}`;
            containers.set(groupKey, []);
            for (const child of childrenOf(field)) {
                inserted.add(child.id);
                containers.get(groupKey)!.push(child.id);
                where.set(child.id, groupKey);
            }
        }
    };

    // 1. new pages, with their new questions (appended; ordered below)
    for (const page of changedTo) {
        if (fromById.has(page.id)) continue;
        const shell = clone(page);
        if (!shell.properties) shell.properties = {};
        shell.properties.fields = childrenOf(page)
            .filter((f) => isNew(f.id))
            .map(newField);
        ops.push({ op: 'insert_page', index: pageOrder.length, page: shell });
        pageOrder.push(page.id);
        const key = `p:${page.id}`;
        containers.set(key, []);
        for (const field of childrenOf(shell)) {
            containers.get(key)!.push(field.id);
            noteInserted(field, key);
        }
    }
    // 2. page questions: new ones inserted, ones from elsewhere moved in
    for (const page of changedTo) {
        const key = `p:${page.id}`;
        childrenOf(page).forEach((field, k) => {
            if (isNew(field.id)) {
                const copy = newField(field);
                ops.push({ op: 'insert_field', pageId: page.id, index: k, field: copy });
                place(field.id, key, k);
                inserted.delete(field.id);
                noteInserted(copy, key);
            } else if (where.get(field.id) !== key) {
                ops.push({ op: 'move_field', fieldId: field.id, toPageId: page.id, index: k });
                noteMove(field.id, where.get(field.id), key);
                unplace(field.id);
                place(field.id, key, k);
            }
        });
    }
    // 3. group questions, likewise
    for (const page of changedTo) {
        for (const group of childrenOf(page).filter(isRepeatingGroup)) {
            const key = `g:${group.id}`;
            if (!containers.has(key)) containers.set(key, []);
            childrenOf(group).forEach((child, k) => {
                if (isNew(child.id)) {
                    ops.push({ op: 'insert_field', groupId: group.id, index: k, field: withoutRules(clone(child)) });
                    place(child.id, key, k);
                    inserted.add(child.id);
                } else if (where.get(child.id) !== key) {
                    ops.push({ op: 'move_field', fieldId: child.id, toGroupId: group.id, index: k });
                    noteMove(child.id, where.get(child.id), key);
                    unplace(child.id);
                    place(child.id, key, k);
                }
            });
        }
    }
    // 4. removed questions (those in a removed group or page go with it), then removed pages
    const gone = (key: string) => {
        const id = key.slice(2);
        return key.startsWith('g:') ? !toIdx.fields.has(id) : !toById.has(id);
    };
    for (const id of fromIdx.fields.keys()) {
        if (toIdx.fields.has(id) || !where.has(id)) continue;
        const key = where.get(id)!;
        if (gone(key)) continue;
        if (key.startsWith('g:') && gone(where.get(key.slice(2)) ?? key)) continue;
        ops.push({ op: 'remove_field', fieldId: id });
        unplace(id);
    }
    for (const page of fromAll) {
        if (toById.has(page.id)) continue;
        ops.push({ op: 'remove_page', pageId: page.id });
        pageOrder.splice(pageOrder.indexOf(page.id), 1);
    }
    // 5. order within each page and group
    const reorder = (key: string, target: string[]) => {
        const list = containers.get(key) ?? [];
        target.forEach((id, k) => {
            if (list[k] === id) return;
            ops.push({ op: 'move_field', fieldId: id, index: k });
            list.splice(list.indexOf(id), 1);
            list.splice(k, 0, id);
        });
    };
    for (const [key, target] of toIdx.containers) if (key.startsWith('p:')) reorder(key, target);
    for (const [key, target] of toIdx.containers) if (key.startsWith('g:')) reorder(key, target);
    // 6. page order
    toAll.forEach((page, k) => {
        if (pageOrder[k] === page.id) return;
        ops.push({ op: 'move_page', pageId: page.id, index: k });
        pageOrder.splice(pageOrder.indexOf(page.id), 1);
        pageOrder.splice(k, 0, page.id);
    });
    // 7. content: pages' own properties and questions that differ
    ops.push(...contentOps(fromById, changedTo, fromIdx, toIdx, forced));
    return ops;
}

/**
 * Ops that turn `prev` into `next`.
 *
 * The engine's own side effects are planned for: a removal drops only what
 * referred to something `next` no longer has (which `next`'s questions do
 * not use), and the date rules a move across a repeating group's boundary
 * drops, or that a question inserted before the one it uses would be
 * refused for, are put back by replacing those questions at the end.
 */
export function entityDiff(prev: FormDoc, next: FormDoc): FormOp[] {
    const ops = formLevelOps(prev, next);
    if (prev.fields !== next.fields) ops.push(...structureOps(prev, next));
    return ops;
}

import React from 'react';

import { act, cleanup, render } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { formDocAtom, resetFromServerAtom, undoAtom } from '@app/store/jotai/form-document';
import { store as reduxStore } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import { useSectionActions } from './use-reusable-sections';

const served = vi.hoisted(() => ({
    toasts: [] as any[],
    calls: [] as Array<[string, any]>,
    fragment: null as any,
    plan: null as any,
    created: null as any,
    saved: null as any,
    failure: null as any
}));
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: (t: any) => served.toasts.push(t) }) }));
vi.mock('@app/store/reusable-sections/api', () => {
    const run = (name: string, key: 'fragment' | 'plan' | 'created' | 'saved') => () => [
        (args: any) => {
            served.calls.push([name, args]);
            return Promise.resolve(served.failure ? { error: served.failure } : { data: served[key] });
        }
    ];
    return {
        useInstantiateSectionMutation: run('instantiate', 'fragment'),
        usePlanSectionUpdateMutation: run('plan', 'plan'),
        useCreateSectionMutation: run('create', 'created'),
        useSaveSectionContentMutation: run('save', 'saved')
    };
});

const q = (id: string, extra: Record<string, unknown> = {}) => ({ id, index: 0, type: 'short_text', title: id, ...extra }) as any;
const mark = (instance: string, key: string, version = 1) => ({ properties: { library: { sectionId: 's1', version, key, instance } } });

let actions: ReturnType<typeof useSectionActions>;
function Harness() {
    actions = useSectionActions();
    return null;
}

const fieldIds = (jotai: ReturnType<typeof createStore>) => ((jotai.get(formDocAtom).fields![0].properties!.fields as any[]) ?? []).map((f) => f.id);

function mount(fields: any[], containers: any[] = []) {
    const jotai = createStore();
    jotai.set(resetFromServerAtom, { formId: 'f1', title: 'T', fields: [{ id: 'p1', index: 0, type: 'slide', properties: { fields, containers } }] } as any);
    render(
        <ReduxProvider store={reduxStore}>
            <Provider store={jotai}>
                <Harness />
            </Provider>
        </ReduxProvider>
    );
    return jotai;
}

beforeEach(() => {
    reduxStore.dispatch(setWorkspace({ id: 'w1', workspaceName: 'acme' } as any));
    served.toasts = [];
    served.calls = [];
    served.failure = null;
    served.fragment = { sectionId: 's1', version: 1, instance: 'i1', fields: [q('n1', mark('i1', 'k1')), q('n2', mark('i1', 'k2'))], containers: [] };
});
afterEach(cleanup);

describe('inserting a library section', () => {
    it('copies it to the end of the selected page as one undoable step', async () => {
        const jotai = mount([q('a'), q('b')]);
        let ok = false;
        await act(async () => {
            ok = await actions.insert('s1', null, { id: 'p1', index: 0 });
        });
        expect(ok).toBe(true);
        expect(served.calls[0]).toEqual(['instantiate', { workspaceId: 'w1', sectionId: 's1' }]);
        expect(fieldIds(jotai)).toEqual(['a', 'b', 'n1', 'n2']);
        expect(served.toasts[0].description).toBe('2 questions inserted from the library.');
        // the marker travels with the questions
        expect((jotai.get(formDocAtom).fields![0].properties!.fields as any[])[2].properties.library.instance).toBe('i1');
    });

    it('goes where the canvas menu was opened', async () => {
        const jotai = mount([q('a'), q('b')]);
        await act(async () => {
            await actions.insert('s1', { slideId: 'p1', slideIndex: 0, fieldIndex: 1, anchorId: 'x' }, null);
        });
        expect(fieldIds(jotai)).toEqual(['a', 'n1', 'n2', 'b']);
    });

    it('says why when the library or the engine refuses, and changes nothing', async () => {
        const jotai = mount([q('a')]);
        served.failure = { data: { message: 'Not found' } };
        await act(async () => {
            expect(await actions.insert('s1', null, { id: 'p1', index: 0 })).toBe(false);
        });
        expect(served.toasts.at(-1).description).toBe('Not found');
        served.failure = null;
        // an id the form already has: the engine refuses
        served.fragment = { ...served.fragment, fields: [q('a')] };
        await act(async () => {
            expect(await actions.insert('s1', null, { id: 'p1', index: 0 })).toBe(false);
        });
        expect(served.toasts.at(-1).description).toContain('already used');
        expect(fieldIds(jotai)).toEqual(['a']);
    });

    it('needs a page to put it on', async () => {
        mount([q('a')]);
        await act(async () => {
            expect(await actions.insert('s1', null, null)).toBe(false);
        });
        expect(served.calls).toEqual([]);
    });
});

describe('updating a copy', () => {
    const copy = () => [q('intro'), q('x1', mark('i1', 'k1')), q('x2', mark('i1', 'k2')), q('outro')];

    it('asks the server for the plan with the copy as the builder holds it', async () => {
        mount(copy());
        served.plan = { sectionId: 's1', version: 2, baseKnown: true, instance: 'i1', changes: [], fields: [], containers: [], replaceIds: [] };
        let plan: any;
        await act(async () => {
            plan = await actions.planUpdate('p1', 'i1');
        });
        expect(plan).toBe(served.plan);
        const [name, args] = served.calls[0];
        expect(name).toBe('plan');
        expect(args.instance).toBe('i1');
        expect(args.sectionId).toBe('s1');
        expect(args.fields.map((f: any) => f.id)).toEqual(['x1', 'x2']);
    });

    it('replaces the copy where it was, keeping the ids the plan keeps', () => {
        const jotai = mount(copy());
        const plan = { sectionId: 's1', version: 2, baseKnown: true, instance: 'i1', changes: [], containers: [], replaceIds: ['x1', 'x2'], fields: [q('x1', { title: 'New title', ...mark('i1', 'k1', 2) }), q('y3', mark('i1', 'k3', 2))] };
        let ok = false;
        act(() => {
            ok = actions.applyUpdate('p1', plan as any);
        });
        expect(ok).toBe(true);
        expect(fieldIds(jotai)).toEqual(['intro', 'x1', 'y3', 'outro']);
        expect((jotai.get(formDocAtom).fields![0].properties!.fields as any[])[1].title).toBe('New title');
        // one undo step puts the copy back
        act(() => {
            jotai.set(undoAtom);
        });
        expect(fieldIds(jotai)).toEqual(['intro', 'x1', 'x2', 'outro']);
    });
});

describe('saving to the library', () => {
    it('sends the chosen questions and the container that holds them', async () => {
        mount([q('a'), q('b'), q('c')], [{ id: 'box', type: 'panel', title: 'Box', fields: ['a', 'b'] }]);
        served.created = { id: 's9', name: 'Pair', warnings: [] };
        let saved: any;
        await act(async () => {
            saved = await actions.saveAsSection({ pageId: 'p1', fieldIds: ['a', 'b'], containerId: 'box', name: 'Pair', description: '' });
        });
        expect(saved.id).toBe('s9');
        const [name, args] = served.calls[0];
        expect(name).toBe('create');
        expect(args.fields.map((f: any) => f.id)).toEqual(['a', 'b']);
        expect(args.containers.map((c: any) => c.id)).toEqual(['box']);
        expect(args.description).toBeUndefined();
    });

    it('saves a copy as the next version against the version it came from, then marks the copy with it', async () => {
        const jotai = mount([q('x1', mark('i1', 'k1', 1)), q('x2', mark('i1', 'k2', 1))]);
        served.saved = { id: 's1', name: 'S', version: 2, warnings: [] };
        await act(async () => {
            await actions.saveCopy('p1', 'i1');
        });
        const [name, args] = served.calls[0];
        expect(name).toBe('save');
        expect(args).toMatchObject({ workspaceId: 'w1', sectionId: 's1', expectedVersion: 1 });
        expect((jotai.get(formDocAtom).fields![0].properties!.fields as any[]).map((f) => f.properties.library.version)).toEqual([2, 2]);
    });

    it('tells the creator to update first when the library moved on', async () => {
        mount([q('x1', mark('i1', 'k1', 1))]);
        served.failure = { data: { code: 'section_changed', message: 'x' } };
        await act(async () => {
            expect(await actions.saveCopy('p1', 'i1')).toBeNull();
        });
        expect(served.toasts.at(-1).description).toContain('Update this copy first');
    });
});

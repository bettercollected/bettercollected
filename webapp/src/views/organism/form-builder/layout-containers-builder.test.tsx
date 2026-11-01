// Layout containers in the builder: the actions (group, ungroup, add a
// question, tabs, move out) as undoable ops on a real document, the frame on
// the canvas, the question's Layout section and the container's inspector.
import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useLayoutContainerActions } from '@app/lib/hooks/use-layout-containers';
import { FieldTypes, LayoutContainer, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { activeContainerAtom } from '@app/store/jotai/active-builder-component';
import { dispatchAtom, formDocAtom, redoAtom, resetFromServerAtom, undoAtom } from '@app/store/jotai/form-document';
import { containersOf, layoutProblems, membersOf } from '@app/utils/layout-containers';
import FieldLayoutSection from '@app/views/molecules/form-builder/field-layout-section';
import LayoutContainerSettings from '@app/views/molecules/form-builder/layout-container-settings';
import LayoutContainerFrame from '@app/views/organism/form-builder/layout-container-frame';

const served = vi.hoisted(() => ({ layoutContainersEnabled: true }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ layoutContainersEnabled: served.layoutContainersEnabled }) }));

const q = (id: string, title = id.toUpperCase()): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title, properties: { fields: [] }, validations: { required: false } }) as any;
const panel = (id: string, title: string, fields: string[]): LayoutContainer => ({ id, type: 'panel', title, fields });
const tabs = (id: string, ...lists: Array<[string, string[]]>): LayoutContainer => ({ id, type: 'tabs', tabs: lists.map(([title, fields], i) => ({ id: `${id}t${i + 1}`, title, fields })) });

const form = (fields: StandardFormFieldDto[], containers?: LayoutContainer[]) =>
    ({ title: 'T', builderVersion: 'v2', fields: [{ id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields: fields.map((f, i) => ({ ...f, index: i })), ...(containers ? { containers } : {}) } }] }) as any;

let store = createStore();
let actions: ReturnType<typeof useLayoutContainerActions>;
function Probe() {
    actions = useLayoutContainerActions();
    return null;
}
const mount = (doc: any, children: React.ReactNode = null) => {
    store = createStore();
    store.set(resetFromServerAtom, doc);
    return render(
        <Provider store={store}>
            <Probe />
            {children}
        </Provider>
    );
};
const page = () => store.get(formDocAtom).fields![0];
const ids = () => (page().properties!.fields as StandardFormFieldDto[]).map((f) => f.id);
const names = { title: 'New panel', tab: (n: number) => `Tab ${n}` };

describe('the builder actions on containers', () => {
    beforeEach(() => {
        served.layoutContainersEnabled = true;
    });
    afterEach(() => vi.clearAllMocks());

    it('groups a question into a new panel, tabs or field set, as one undoable step', () => {
        mount(form([q('a'), q('b'), q('c')]));
        act(() => void actions.group('p1', 'panel', ['b'], names));
        expect(containersOf(page())).toEqual([{ id: 'c1', type: 'panel', title: 'New panel', fields: ['b'] }]);
        act(() => void actions.group('p1', 'tabs', ['c'], names));
        expect(containersOf(page()).map((c) => [c.id, c.type])).toEqual([
            ['c1', 'panel'],
            ['c2', 'tabs']
        ]);
        expect(containersOf(page())[1].tabs!.map((t) => [t.id, t.title, t.fields])).toEqual([
            ['t1', 'Tab 1', ['c']],
            ['t2', 'Tab 2', []]
        ]);
        expect(layoutProblems(store.get(formDocAtom).fields as any)).toEqual([]);
        act(() => void store.set(undoAtom));
        expect(containersOf(page()).map((c) => c.id)).toEqual(['c1']);
        act(() => void store.set(undoAtom));
        expect(containersOf(page())).toEqual([]);
        act(() => void store.set(redoAtom));
        expect(containersOf(page()).map((c) => c.id)).toEqual(['c1']);
    });

    it('adds a new container with a new question at a position', () => {
        mount(form([q('a'), q('b')]));
        let id: string | null = null;
        act(() => void (id = actions.insertNew('p1', 'fieldset', 1, names)));
        expect(ids()).toEqual(['a', id, 'b']);
        expect(membersOf(containersOf(page())[0])).toEqual([id]);
    });

    it('adds a question at the end of a container and keeps it a member, also in an empty tab', () => {
        mount(form([q('a'), q('b'), q('c')], [panel('c1', 'P', ['a', 'b']), tabs('c2', ['T1', ['c']], ['T2', []])]));
        let added: string | null = null;
        act(() => void (added = actions.addQuestion('p1', 'c1')));
        expect(ids()).toEqual(['a', 'b', added, 'c']);
        expect(membersOf(containersOf(page())[0])).toEqual(['a', 'b', added]);
        let inTab: string | null = null;
        act(() => void (inTab = actions.addQuestion('p1', 'c2', 'c2t2')));
        expect(ids()).toEqual(['a', 'b', added, 'c', inTab]);
        expect(containersOf(page())[1].tabs!.map((t) => t.fields)).toEqual([['c'], [inTab]]);
        expect(layoutProblems(store.get(formDocAtom).fields as any)).toEqual([]);
    });

    it('ungroups, taking the container away and keeping the questions', () => {
        mount(form([q('a'), q('b')], [panel('c1', 'P', ['a', 'b'])]));
        act(() => void actions.ungroup('p1', 'c1'));
        expect(containersOf(page())).toEqual([]);
        expect(ids()).toEqual(['a', 'b']);
    });

    it('adds, removes and moves tabs; a removed tab hands its questions to the tab before it', () => {
        mount(form([q('a'), q('b'), q('c')], [tabs('c1', ['One', ['a']], ['Two', ['b']], ['Three', ['c']])]));
        act(() => void actions.addTab('p1', 'c1', 'Four'));
        expect(containersOf(page())[0].tabs!.map((t) => t.title)).toEqual(['One', 'Two', 'Three', 'Four']);
        act(() => void actions.removeTab('p1', 'c1', 'c1t2'));
        expect(containersOf(page())[0].tabs!.map((t) => [t.title, t.fields])).toEqual([
            ['One', ['a', 'b']],
            ['Three', ['c']],
            ['Four', []]
        ]);
        act(() => void actions.moveTab('p1', 'c1', 'c1t3', -1));
        expect(containersOf(page())[0].tabs!.map((t) => t.title)).toEqual(['Three', 'One', 'Four']);
        expect(ids()).toEqual(['c', 'a', 'b']);
        expect(layoutProblems(store.get(formDocAtom).fields as any)).toEqual([]);
    });

    it('moves a question out of its container to just before it', () => {
        mount(form([q('x'), q('a'), q('b'), q('c')], [panel('c1', 'P', ['a', 'b', 'c'])]));
        act(() => void actions.moveOut('p1', 'b'));
        expect(ids()).toEqual(['x', 'b', 'a', 'c']);
        expect(membersOf(containersOf(page())[0])).toEqual(['a', 'c']);
        act(() => void actions.moveOut('p1', 'a'));
        // the first member steps up past the question before the container
        expect(ids()).toEqual(['x', 'a', 'b', 'c']);
        expect(membersOf(containersOf(page())[0])).toEqual(['c']);
        expect(layoutProblems(store.get(formDocAtom).fields as any)).toEqual([]);
    });

    it('a title is saved as it is typed, one undo step for the burst', () => {
        mount(form([q('a')], [panel('c1', 'P', ['a'])]));
        act(() => void actions.update('p1', 'c1', { title: 'Co' }, 'Edit title', 'container-title-c1'));
        act(() => void actions.update('p1', 'c1', { title: 'Cont' }, 'Edit title', 'container-title-c1'));
        expect(containersOf(page())[0].title).toBe('Cont');
        act(() => void store.set(undoAtom));
        expect(containersOf(page())[0].title).toBe('P');
    });

    it('an edit the engine refuses changes nothing', () => {
        mount(form([q('a'), q('b'), q('c')], [panel('c1', 'P', ['a', 'b'])]));
        let ok = true;
        act(() => void (ok = store.set(dispatchAtom, { ops: [{ op: 'set_page_containers', pageId: 'p1', containers: [{ type: 'panel', title: 'Gap', fields: ['a', 'c'] }] }] as any, label: 'x' })));
        expect(ok).toBe(false);
        expect(containersOf(page()).map((c) => c.id)).toEqual(['c1']);
    });
});

describe('the frame on the canvas', () => {
    beforeEach(() => {
        served.layoutContainersEnabled = true;
    });

    const frame = (container: LayoutContainer, editable = true) => (
        <LayoutContainerFrame page={page()} container={container} members={membersOf(container)} editable={editable} renderMembers={(list) => list.map((id) => <div key={id} data-testid={`member-${id}`} />)} />
    );

    it('shows a panel with its title, its collapsed switch and its questions', () => {
        const container = panel('c1', 'Contact', ['a', 'b']);
        mount(form([q('a'), q('b')], [container]));
        render(<Provider store={store}>{frame(container)}</Provider>);
        expect(screen.getByRole('region', { name: 'Panel: Contact' })).toBeInTheDocument();
        expect(screen.getByRole('textbox', { name: 'Title Panel' })).toHaveValue('Contact');
        expect(screen.getByTestId('member-a')).toBeInTheDocument();
        act(() => void fireEvent.click(screen.getByRole('checkbox', { name: 'Closed when the page opens' })));
        expect(containersOf(page())[0].collapsed).toBe(true);
    });

    it('renames from the title box, never stores a blank title and says so', () => {
        const container = panel('c1', 'Contact', ['a']);
        mount(form([q('a')], [container]));
        render(<Provider store={store}>{frame(container)}</Provider>);
        const input = screen.getByRole('textbox', { name: 'Title Panel' });
        act(() => void fireEvent.change(input, { target: { value: 'People' } }));
        expect(containersOf(page())[0].title).toBe('People');
        act(() => void fireEvent.change(input, { target: { value: '   ' } }));
        expect(containersOf(page())[0].title).toBe('People');
        expect(input).toHaveAttribute('aria-invalid', 'true');
        expect(screen.getByText('A title is needed')).toBeInTheDocument();
    });

    it('ungroups from the frame', () => {
        const container = panel('c1', 'Contact', ['a']);
        mount(form([q('a')], [container]));
        render(<Provider store={store}>{frame(container)}</Provider>);
        act(() => void fireEvent.click(screen.getByRole('button', { name: /Ungroup Contact/ })));
        expect(containersOf(page())).toEqual([]);
    });

    it('shows tabs one group each, with the tab controls and a note for a single tab', () => {
        const container = tabs('c1', ['One', ['a']], ['Two', []]);
        mount(form([q('a')], [container]));
        render(<Provider store={store}>{frame(container)}</Provider>);
        const one = screen.getByRole('group', { name: 'One' });
        expect(within(one).getByTestId('member-a')).toBeInTheDocument();
        expect(within(screen.getByRole('group', { name: 'Two' })).getByText('No questions in this tab yet')).toBeInTheDocument();
        expect(screen.getAllByRole('button', { name: 'Move tab earlier' })[0]).toBeDisabled();
        act(() => void fireEvent.click(screen.getByRole('button', { name: /Remove the tab Two/ })));
        expect(containersOf(page())[0].tabs).toHaveLength(1);
    });

    it('leaves the controls out of a preview and out of a server that has no containers', () => {
        const container = panel('c1', 'Contact', ['a']);
        mount(form([q('a')], [container]));
        const { rerender } = render(<Provider store={store}>{frame(container, false)}</Provider>);
        expect(screen.queryByRole('textbox')).toBeNull();
        served.layoutContainersEnabled = false;
        rerender(<Provider store={store}>{frame(container, true)}</Provider>);
        expect(screen.getByRole('textbox', { name: 'Title Panel' })).toBeDisabled();
        expect(screen.getByRole('button', { name: /Add a question to Contact/ })).toBeDisabled();
        // taking it away is still possible
        expect(screen.getByRole('button', { name: /Ungroup Contact/ })).toBeEnabled();
    });
});

describe('the question and container inspectors', () => {
    beforeEach(() => {
        served.layoutContainersEnabled = true;
    });

    it('offers a question a panel, field set or tabs, and says where a grouped one is', () => {
        mount(form([q('a'), q('b')], [panel('c1', 'Contact', ['b'])]), <FieldLayoutSection field={q('a')} pageId="p1" />);
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Put in a field set' })));
        expect(containersOf(page()).map((c) => c.type)).toContain('fieldset');
    });

    it('lets a grouped question leave and is silent while the server has no containers for a question outside one', () => {
        const doc = form([q('a'), q('b')], [panel('c1', 'Contact', ['a', 'b'])]);
        mount(doc, <FieldLayoutSection field={q('a')} pageId="p1" />);
        expect(screen.getByText(/In the panel "Contact"/)).toBeInTheDocument();
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Move out of it' })));
        expect(membersOf(containersOf(page())[0])).toEqual(['b']);
    });

    it('hides the Layout section from a question outside any container while the switch is off', () => {
        served.layoutContainersEnabled = false;
        mount(form([q('a')]), <FieldLayoutSection field={q('a')} pageId="p1" />);
        expect(screen.queryByText('Layout')).toBeNull();
    });

    it('sets a container visible only by an earlier answer, from the questions above it', () => {
        mount(form([q('gate'), q('a'), q('b')], [panel('c1', 'P', ['a', 'b'])]), <LayoutContainerSettings />);
        act(() => void store.set(activeContainerAtom, { pageId: 'p1', id: 'c1' }));
        act(() => void fireEvent.click(screen.getByRole('switch')));
        // half a condition is not saved
        expect(containersOf(page())[0].logic).toBeUndefined();
        expect(screen.getByText('Fill in every condition and the rule applies.')).toBeInTheDocument();
        act(() => void fireEvent.change(screen.getByRole('textbox', { name: /value/i }), { target: { value: 'yes' } }));
        const logic = containersOf(page())[0].logic;
        expect(logic?.action).toBe('SHOW');
        expect(logic?.conditions[0]).toMatchObject({ fieldId: 'gate', comparison: 'IS_EQUAL', value: 'yes' });
        expect(layoutProblems(store.get(formDocAtom).fields as any)).toEqual([]);
        // turned off again
        act(() => void fireEvent.click(screen.getByRole('switch')));
        expect(containersOf(page())[0].logic).toBeUndefined();
    });
});

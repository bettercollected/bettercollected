// Flow view and endings: each ending is a terminal node (the old "submit"
// node is the default ending), jumps that name an ending draw to its node,
// and connecting a page to an ending's node creates such a jump.
import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeAll, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT, LogicalOperator } from '@app/models/types/form-builder-shared';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { store } from '@app/store/store';

import FlowView from './flow-view';

// jsdom cannot lay out React Flow: record what it is given instead.
const flow: { nodes: any[]; edges: any[]; onConnect?: (c: any) => void } = { nodes: [], edges: [] };
vi.mock('@xyflow/react', async (original) => {
    const actual = (await original()) as any;
    return {
        ...actual,
        ReactFlow: (props: any) => {
            flow.nodes = props.nodes;
            flow.edges = props.edges;
            flow.onConnect = props.onConnect;
            return null;
        },
        Background: () => null,
        Controls: () => null,
        MiniMap: () => null
    };
});
vi.mock('@app/views/organism/form-builder/slide-builder', () => ({ default: () => null }));
vi.mock('@app/views/organism/form-builder/properties-drawer', () => ({ default: () => null }));

const rule = (extra: Record<string, any> = {}) => ({ operator: LogicalOperator.AND, conditions: [{ fieldId: 'member', fieldType: FieldTypes.YES_NO, comparison: 'IS_EQUAL', value: 'No' }], target: JUMP_TARGET_SUBMIT, ...extra });
const pages = (jumps: any[]): StandardFormFieldDto[] =>
    [
        { id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'member', index: 0, type: FieldTypes.YES_NO, title: 'Member?' }], jumps } },
        { id: 'p2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [] } }
    ] as any;

const seen: any = {};
function Harness({ jumps, endings }: { jumps: any[]; endings: any[] }) {
    const builder = useFormFieldsAtom();
    const { setFormState } = useFormState();
    seen.builder = builder;
    const [ready, setReady] = React.useState(false);
    React.useEffect(() => {
        builder.initFormFields(pages(jumps));
        setFormState((prev) => ({ ...prev, thankyouPage: endings }));
        setReady(true);
    }, []);
    return ready ? <FlowView /> : null;
}

const renderFlow = async (jumps: any[], endings: any[]) => {
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Harness jumps={jumps} endings={endings} />
            </Provider>
        </ReduxProvider>
    );
    // edges follow the nodes one animation frame later
    await act(async () => new Promise((resolve) => setTimeout(resolve, 50)));
};

const terminals = () => flow.nodes.filter((n) => n.data?.kind === 'end').map((n) => [n.id, n.data.label, !!n.data.isDefault, !!n.data.unreached]);
const jumpEdges = () => flow.edges.filter((e) => e.id.startsWith('jump-')).map((e) => [e.source, e.target]);

beforeAll(() => {
    (globalThis as any).ResizeObserver ??= class {
        observe() {}
        disconnect() {}
    };
});

describe('flow view endings', () => {
    const ENDINGS = [
        { id: 'thanks', name: 'Thanks' },
        { id: 'sorry', name: 'Not eligible' },
        { id: 'later', name: 'Waiting list' }
    ];

    it('draws every ending as a terminal node, the default one as the end of the spine', async () => {
        await renderFlow([rule({ endingId: 'sorry' })], ENDINGS);
        expect(terminals()).toEqual([
            ['__end__', 'Thanks', true, false],
            ['__ending__:sorry', 'Not eligible', false, false],
            ['__ending__:later', 'Waiting list', false, true]
        ]);
        expect(jumpEdges()).toEqual([['p1', '__ending__:sorry']]);
        // the linear spine ends at the default ending
        expect(flow.edges.find((e) => e.id === 'next-2')?.target).toBe('__end__');
    });

    it('a plain submit jump goes to the default ending; one to a missing ending is not drawn', async () => {
        await renderFlow([rule(), rule({ endingId: 'gone' })], ENDINGS);
        expect(jumpEdges()).toEqual([['p1', '__end__']]);
        expect(flow.nodes.find((n) => n.id === 'p1')?.data.brokenCount).toBe(1);
    });

    it('connecting a page to an ending node creates a jump that shows it', async () => {
        await renderFlow([], ENDINGS);
        act(() => flow.onConnect!({ source: 'p1', target: '__ending__:later', sourceHandle: 'jump-out', targetHandle: 'jump-in' }));
        expect(seen.builder.formFields[0].properties.jumps).toEqual([expect.objectContaining({ target: JUMP_TARGET_SUBMIT, endingId: 'later' })]);
        act(() => flow.onConnect!({ source: 'p2', target: '__end__', sourceHandle: 'jump-out', targetHandle: 'jump-in' }));
        const jump = seen.builder.formFields[1].properties.jumps[0];
        expect(jump.target).toBe(JUMP_TARGET_SUBMIT);
        expect(jump).not.toHaveProperty('endingId');
    });

    it('with one ending, keeps the single end node', async () => {
        await renderFlow([], [{ title: 'Thanks' }]);
        expect(terminals()).toEqual([['__end__', 'Thank you', false, false]]);
    });
});

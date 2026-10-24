// Flow view page nodes: the first question names the node, the next two are
// listed under it, and "+N more" counts only the questions not shown.
import React from 'react';

import { act, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeAll, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { store } from '@app/store/store';

import FlowView from './flow-view';

// jsdom cannot lay out React Flow: render each node with its own component instead.
vi.mock('@xyflow/react', async (original) => {
    const actual = (await original()) as any;
    return {
        ...actual,
        ReactFlow: (props: any) => (
            <div>
                {props.nodes.map((node: any) => {
                    const NodeComponent = props.nodeTypes[node.type];
                    return (
                        <div key={node.id} data-testid={`node-${node.id}`}>
                            <NodeComponent id={node.id} data={node.data} selected={false} />
                        </div>
                    );
                })}
            </div>
        ),
        Handle: () => null,
        Background: () => null,
        Controls: () => null,
        MiniMap: () => null
    };
});
vi.mock('@app/views/organism/form-builder/slide-builder', () => ({ default: () => null }));
vi.mock('@app/views/organism/form-builder/properties-drawer', () => ({ default: () => null }));

const page = (id: string, index: number, count: number): StandardFormFieldDto =>
    ({
        id,
        index,
        type: FieldTypes.SLIDE,
        properties: { fields: Array.from({ length: count }, (_, i) => ({ id: `${id}-q${i + 1}`, index: i, type: FieldTypes.SHORT_TEXT, title: `${id} question ${i + 1}` })) }
    }) as any;

function Harness({ pages }: { pages: StandardFormFieldDto[] }) {
    const builder = useFormFieldsAtom();
    const [ready, setReady] = React.useState(false);
    React.useEffect(() => {
        builder.initFormFields(pages);
        setReady(true);
    }, []);
    return ready ? <FlowView /> : null;
}

const renderFlow = async (pages: StandardFormFieldDto[]) => {
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Harness pages={pages} />
            </Provider>
        </ReduxProvider>
    );
    await act(async () => new Promise((resolve) => setTimeout(resolve, 50)));
};

beforeAll(() => {
    (globalThis as any).ResizeObserver ??= class {
        observe() {}
        disconnect() {}
    };
});

describe('flow view page nodes', () => {
    it('counts in "+N more" only the questions the node does not show', async () => {
        await renderFlow([page('p1', 0, 1), page('p2', 1, 2), page('p3', 2, 3), page('p4', 3, 4), page('p5', 4, 6)]);
        const node = (id: string) => within(screen.getByTestId(`node-${id}`));

        // one question: it names the node, nothing more
        expect(node('p1').getByText('p1 question 1')).toBeTruthy();
        expect(node('p1').queryByText(/more$/)).toBeNull();
        // two: the name and one listed
        expect(node('p2').getByText('· p2 question 2')).toBeTruthy();
        expect(node('p2').queryByText(/more$/)).toBeNull();
        // three: the name and two listed
        expect(node('p3').getByText('· p3 question 3')).toBeTruthy();
        expect(node('p3').queryByText(/more$/)).toBeNull();
        // four: one not shown
        expect(node('p4').getByText('+1 more')).toBeTruthy();
        // six: three not shown
        expect(node('p5').getByText('+3 more')).toBeTruthy();
        expect(node('p5').getByText('6 questions')).toBeTruthy();
    });
});

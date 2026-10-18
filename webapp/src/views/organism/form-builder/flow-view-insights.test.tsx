// Flow view insights: the counts come from the server's submission paths
// (page ids, jumps taken, ending reached), never from answers; without
// response.read the paths are not requested and the view shows no counts.
import React from 'react';

import { skipToken } from '@reduxjs/toolkit/query/react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT, LogicalOperator } from '@app/models/types/form-builder-shared';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { store } from '@app/store/store';
import { SubmissionPath } from '@app/utils/conditional-logic';

import FlowView from './flow-view';

const flow: { nodes: any[]; edges: any[] } = { nodes: [], edges: [] };
vi.mock('@xyflow/react', async (original) => {
    const actual = (await original()) as any;
    return {
        ...actual,
        ReactFlow: (props: any) => {
            flow.nodes = props.nodes;
            flow.edges = props.edges;
            return null;
        },
        Background: () => null,
        Controls: () => null,
        MiniMap: () => null
    };
});
vi.mock('@app/views/organism/form-builder/slide-builder', () => ({ default: () => null }));
vi.mock('@app/views/organism/form-builder/properties-drawer', () => ({ default: () => null }));

const server = vi.hoisted(() => ({ paths: [] as any[], permissions: new Set<string>(), requests: [] as any[] }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (p: string) => server.permissions.has(p), permissions: server.permissions, isLoading: false })
}));
vi.mock('@app/store/workspaces/api', async (original) => ({
    ...((await original()) as any),
    useGetFormSubmissionPathsQuery: (arg: any, options: any) => {
        if (arg === skipToken || options?.skip) return { data: undefined, isFetching: false };
        server.requests.push(arg);
        return { data: server.paths, isFetching: false };
    }
}));
vi.mock('@app/store/redux/form-api', async (original) => ({
    ...((await original()) as any),
    useGetFlowAnalyticsQuery: () => ({ data: undefined })
}));
const ids = vi.hoisted(() => ({ workspace: { id: 'ws1' }, form: { formId: 'form1' } }));
vi.mock('@app/store/workspaces/slice', async (original) => ({ ...((await original()) as any), selectWorkspace: () => ids.workspace }));
vi.mock('@app/store/forms/slice', async (original) => ({ ...((await original()) as any), selectForm: () => ids.form }));

const pages = (): StandardFormFieldDto[] =>
    [
        {
            id: 'p1',
            index: 0,
            type: FieldTypes.SLIDE,
            properties: {
                fields: [{ id: 'member', index: 0, type: FieldTypes.YES_NO, title: 'Member?' }],
                jumps: [{ operator: LogicalOperator.AND, conditions: [{ fieldId: 'member', fieldType: FieldTypes.YES_NO, comparison: 'IS_EQUAL', value: 'No' }], target: JUMP_TARGET_SUBMIT, endingId: 'sorry' }]
            }
        },
        { id: 'p2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [] } }
    ] as any;

function Harness() {
    const builder = useFormFieldsAtom();
    const { setFormState } = useFormState();
    const [ready, setReady] = React.useState(false);
    React.useEffect(() => {
        builder.initFormFields(pages());
        setFormState((prev) => ({
            ...prev,
            thankyouPage: [
                { id: 'thanks', name: 'Thanks' },
                { id: 'sorry', name: 'Not eligible' }
            ]
        }));
        setReady(true);
    }, []);
    return ready ? <FlowView /> : null;
}

const renderFlow = async () => {
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Harness />
            </Provider>
        </ReduxProvider>
    );
    await act(async () => new Promise((resolve) => setTimeout(resolve, 50)));
};

const showInsights = async () => {
    fireEvent.click(screen.getByRole('button', { name: /insights/i }));
    await act(async () => new Promise((resolve) => setTimeout(resolve, 50)));
};

const node = (id: string) => flow.nodes.find((n) => n.id === id)?.data;
const edgeLabel = (id: string) => flow.edges.find((e) => e.id === id)?.label;

// two submissions ended on "Not eligible" through the jump, one went through
// both pages to the default ending (the server leaves out null fields)
const PATHS: SubmissionPath[] = [
    { steps: [{ pageId: 'p1', jump: 0 }], ended: true, endingId: 'sorry' },
    { steps: [{ pageId: 'p1', jump: 0 }], ended: true, endingId: 'sorry' },
    { steps: [{ pageId: 'p1' }, { pageId: 'p2' }], ended: true }
];

beforeAll(() => {
    (globalThis as any).ResizeObserver ??= class {
        observe() {}
        disconnect() {}
    };
});

beforeEach(() => {
    server.paths = PATHS;
    server.requests = [];
    server.permissions = new Set(['response.read', 'analytics.read']);
});

describe('flow view insights', () => {
    it('paints the counts of the submission paths on nodes, edges and endings', async () => {
        await renderFlow();
        expect(node('p1').visits).toBeUndefined();
        await showInsights();

        expect(server.requests[0]).toMatchObject({ workspaceId: 'ws1', formId: 'form1' });
        expect(node('__welcome__').totalResponses).toBe(3);
        expect(node('p1').visits).toBe(3);
        expect(node('p2').visits).toBe(1);
        expect(edgeLabel('next-0')).toBe('3'); // welcome → p1
        expect(edgeLabel('next-1')).toBe('1'); // p1 → p2
        expect(flow.edges.find((e) => e.id.startsWith('jump-'))?.label).toMatch(/· 2$/);
        expect(node('__ending__:sorry').totalResponses).toBe(2);
        expect(node('__end__').totalResponses).toBe(1);
        expect(screen.getByText('3')).toBeTruthy();
    });

    it('without response.read asks for no paths and shows no counts or errors', async () => {
        server.permissions = new Set(['analytics.read']);
        await renderFlow();
        await showInsights();

        expect(server.requests).toEqual([]);
        expect(node('p1').visits).toBeUndefined();
        expect(edgeLabel('next-0')).toBeUndefined();
        expect(screen.queryByText(/no responses yet/i)).toBeNull();
    });

    it('with no submissions says so', async () => {
        server.paths = [];
        await renderFlow();
        await showInsights();

        expect(node('p1').visits).toBe(0);
        expect(screen.getByText(/no responses yet/i)).toBeTruthy();
    });
});

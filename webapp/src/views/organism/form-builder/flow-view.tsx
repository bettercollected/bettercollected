'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { FieldTypes, V2InputFields } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { JUMP_TARGET_SUBMIT, LogicalOperator, PageJump } from '@app/models/types/form-builder-shared';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useGetFormAllSubmissionsQuery } from '@app/store/workspaces/api';
import { computeFlowTraffic, fieldHasLogic, FlowTraffic, isJumpTargetValid } from '@app/utils/conditional-logic';
import { buildSourceFields, fieldText, newConditionFor, pageLabel } from '@app/views/molecules/form-builder/condition-editor-shared';
import PageJumpEditor from '@app/views/molecules/form-builder/page-jump-editor';
import PropertiesDrawer from '@app/views/organism/form-builder/properties-drawer';
import SlideBuilder from '@app/views/organism/form-builder/slide-builder';
import { AlertTriangle, BarChart3, Copy, LayoutGrid, PencilLine, Plus, Trash2, X } from 'lucide-react';
import { v4 } from 'uuid';

import { Background, BackgroundVariant, Connection, Controls, Edge, Handle, MarkerType, MiniMap, Node, NodeProps, Position, ReactFlow, useEdgesState, useNodesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// Deterministic default layout (used when a page has no saved position).
const NODE_W = 300;
const NODE_H = 96;
const GAP_Y = 72;
const COL_X = 120;
const JUMP_COLOR = '#0764eb';
const NEXT_COLOR = '#c2cad9';

const defaultPos = (k: number) => ({ x: COL_X, y: 40 + k * (NODE_H + GAP_Y) });

/* ----------------------------- custom nodes ------------------------------ */

function PageNode({ data, selected }: NodeProps<Node<any>>) {
    return (
        <div className={'flex w-[300px] flex-col gap-1 rounded-xl border bg-white px-4 py-3 shadow-sm transition-shadow ' + (selected ? 'border-brand-500 shadow-bubble' : 'border-black-200 hover:border-brand-300')}>
            <Handle id="next-in" type="target" position={Position.Top} isConnectable={false} style={{ opacity: 0 }} />
            <Handle id="jump-in" type="target" position={Position.Left} style={{ background: JUMP_COLOR, width: 9, height: 9 }} />
            {/* Invisible right-side anchor: edges from pages in the same column enter
                here so they bow beside the column instead of crossing it. Users still
                drop connections on the visible left dot. */}
            <Handle id="jump-in-right" type="target" position={Position.Right} isConnectable={false} style={{ opacity: 0, top: '35%' }} />
            <span className="text-black-400 text-[10px] font-semibold uppercase tracking-wide">Page {data.pageNumber}</span>
            <span className="text-black-900 truncate text-sm font-semibold">{data.label}</span>
            {data.questions?.length > 0 && (
                <div className="flex flex-col gap-0.5">
                    {data.questions.map((q: string, i: number) => (
                        <span key={i} className="text-black-500 truncate text-[11px]">
                            · {q}
                        </span>
                    ))}
                    {data.questionCount > data.questions.length && <span className="text-black-400 text-[11px]">+{data.questionCount - data.questions.length} more</span>}
                </div>
            )}
            <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                <span className="text-black-500">
                    {data.questionCount} question{data.questionCount === 1 ? '' : 's'}
                </span>
                {data.showHideCount > 0 && <span className="text-brand-600 bg-brand-100 rounded px-1.5 py-[1px] font-medium">{data.showHideCount} show/hide</span>}
                {data.brokenCount > 0 && (
                    <span className="inline-flex items-center gap-0.5 rounded bg-red-50 px-1.5 py-[1px] font-medium text-red-600">
                        <AlertTriangle className="h-3 w-3" /> broken jump
                    </span>
                )}
                {data.visits !== undefined && (
                    <span className="text-black-700 bg-black-100 rounded px-1.5 py-[1px] font-semibold" title="Submissions whose path visited this page">
                        {data.visits}/{data.totalResponses} visited
                    </span>
                )}
            </div>
            <Handle id="jump-out" type="source" position={Position.Right} style={{ background: JUMP_COLOR, width: 9, height: 9 }} />
            <Handle id="next-out" type="source" position={Position.Bottom} isConnectable={false} style={{ opacity: 0 }} />
        </div>
    );
}

function TerminalNode({ data }: NodeProps<Node<any>>) {
    const isEnd = data.kind === 'end';
    return (
        <div className="bg-new-white-200 border-black-200 text-black-600 flex w-[300px] flex-col gap-0.5 rounded-xl border px-4 py-3">
            {isEnd && <Handle id="next-in" type="target" position={Position.Top} isConnectable={false} style={{ opacity: 0 }} />}
            {isEnd && <Handle id="jump-in" type="target" position={Position.Left} style={{ background: JUMP_COLOR, width: 9, height: 9 }} />}
            {isEnd && <Handle id="jump-in-right" type="target" position={Position.Right} isConnectable={false} style={{ opacity: 0, top: '35%' }} />}
            <span className="text-black-400 text-[10px] font-semibold uppercase tracking-wide">{isEnd ? 'End' : 'Start'}</span>
            <span className="text-black-700 text-sm font-semibold">{data.label}</span>
            {data.totalResponses !== undefined && (
                <span className="text-black-700 bg-black-100 w-fit rounded px-1.5 py-[1px] text-[11px] font-semibold">
                    {data.totalResponses} response{data.totalResponses === 1 ? '' : 's'}
                </span>
            )}
            {!isEnd && <Handle id="next-out" type="source" position={Position.Bottom} isConnectable={false} style={{ opacity: 0 }} />}
        </div>
    );
}

const nodeTypes = { page: PageNode, terminal: TerminalNode };

/* ------------------------------- flow view ------------------------------- */

export default function FlowView({ onClose }: { onClose?: () => void }) {
    const { formFields, addSlide, deleteSlide, duplicateSlide, updateSlideJumps, updateSlidePosition, clearSlidePositions } = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();

    const slides = formFields || [];
    const slideIds = useMemo(() => new Set(slides.map((s) => s.id)), [slides]);

    // Insights: replay submitted answers through the SAME jump evaluator the
    // responder uses, then paint traversal counts on nodes and edges.
    const [showInsights, setShowInsights] = useState(false);
    const workspace = useAppSelector(selectWorkspace);
    const standardForm = useAppSelector(selectForm);
    const { data: submissions, isFetching: insightsLoading } = useGetFormAllSubmissionsQuery({ workspaceId: workspace?.id, formId: standardForm?.formId } as any, {
        skip: !showInsights || !workspace?.id || !standardForm?.formId
    });
    const traffic: FlowTraffic | null = useMemo(() => {
        if (!showInsights || !Array.isArray(submissions)) return null;
        return computeFlowTraffic(slides, submissions.map((s: any) => s?.answers ?? {}));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [showInsights, submissions, slides]);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const selectedIndex = slides.findIndex((s) => s.id === selectedId);
    const selectedSlide = selectedIndex >= 0 ? slides[selectedIndex] : undefined;

    // Page-editor overlay (double-click / "Edit content") — edit a page without
    // leaving the flow. Reuses the builder's SlideBuilder + PropertiesDrawer.
    const [overlayId, setOverlayId] = useState<string | null>(null);
    const overlayIndex = slides.findIndex((s) => s.id === overlayId);
    const overlaySlide = overlayIndex >= 0 ? slides[overlayIndex] : undefined;

    // Same scale-to-fit trick as the main editor: the slide lays out at viewport
    // size and is CSS-scaled into the available overlay area.
    const overlayScaleStyle = useMemo(() => {
        if (typeof window === 'undefined' || !overlaySlide) return undefined;
        const availW = window.innerWidth - 280 - 120; // properties drawer + margins
        const availH = window.innerHeight - 150;
        if (availW / (16 / 9) > availH) {
            return { height: '100vh', scale: availH / window.innerHeight, transformOrigin: 'top left' } as React.CSSProperties;
        }
        return { width: '100vw', scale: availW / window.innerWidth, transformOrigin: 'top left' } as React.CSSProperties;
    }, [overlaySlide]);

    /* ------------ derive nodes/edges from the form model ------------ */

    const buildNodes = useCallback((): Node[] => {
        const pageNodes: Node[] = slides.map((slide, i) => ({
            id: slide.id,
            type: 'page',
            position: (slide.properties?.position as { x: number; y: number } | undefined) ?? defaultPos(i + 1),
            data: {
                label: pageLabel(slide, i).replace(/^Page \d+ · /, '') || 'Untitled page',
                pageNumber: i + 1,
                questionCount: slide.properties?.fields?.length ?? 0,
                questions: (slide.properties?.fields ?? []).slice(1, 3).map((f) => fieldText(f)),
                showHideCount: slide.properties?.fields?.filter((f) => fieldHasLogic(f)).length ?? 0,
                brokenCount: ((slide.properties?.jumps as PageJump[] | undefined) ?? []).filter((j) => j?.conditions?.length && !isJumpTargetValid(j.target, slideIds)).length,
                visits: traffic ? traffic.nodeVisits.get(slide.id) ?? 0 : undefined,
                totalResponses: traffic?.total
            }
        }));
        return [
            { id: '__welcome__', type: 'terminal', position: defaultPos(0), data: { kind: 'welcome', label: 'Welcome', totalResponses: traffic?.total }, deletable: false },
            ...pageNodes.map((n) => ({ ...n, deletable: false })), // deletion goes through the panel (with cleanup), not the Delete key
            { id: '__end__', type: 'terminal', position: defaultPos(slides.length + 1), data: { kind: 'end', label: 'Thank you', totalResponses: traffic?.total }, deletable: false }
        ];
    }, [slides, slideIds, traffic]);

    const buildEdges = useCallback((): Edge[] => {
        const edges: Edge[] = [];
        // Implicit linear spine: welcome → p1 → … → end. Not stored, not deletable.
        const chain = ['__welcome__', ...slides.map((s) => s.id), '__end__'];
        chain.slice(0, -1).forEach((from, i) => {
            const count = traffic ? traffic.nextTraversals.get(from) ?? 0 : undefined;
            edges.push({
                id: `next-${i}`,
                source: from,
                target: chain[i + 1],
                sourceHandle: 'next-out',
                targetHandle: 'next-in',
                deletable: false,
                selectable: false,
                focusable: false,
                label: count !== undefined ? String(count) : undefined,
                labelStyle: { fill: '#7c8598', fontSize: 10.5, fontWeight: 600 },
                labelBgStyle: { fill: '#ffffff', stroke: NEXT_COLOR },
                labelBgPadding: [5, 2] as [number, number],
                labelBgBorderRadius: 6,
                style: { stroke: NEXT_COLOR, strokeWidth: count ? Math.min(1.5 + (3 * count) / Math.max(traffic!.total, 1), 4.5) : 1.5 },
                markerEnd: { type: MarkerType.ArrowClosed, color: NEXT_COLOR, width: 16, height: 16 }
            });
        });
        // Jump edges (only valid targets draw; broken ones surface as a node badge).
        // Routing: same-column (or leftward) targets are entered from the RIGHT so
        // the edge bows beside the column instead of crossing pages; only targets
        // laid out clearly to the right are entered from the left (straight shot).
        const indexById = new Map(slides.map((s, i) => [s.id, i]));
        const posOf = (id: string): { x: number; y: number } => {
            if (id === '__end__') return defaultPos(slides.length + 1);
            const idx = indexById.get(id) ?? 0;
            return (slides[idx]?.properties?.position as { x: number; y: number } | undefined) ?? defaultPos(idx + 1);
        };
        slides.forEach((slide, sIdx) => {
            ((slide.properties?.jumps as PageJump[] | undefined) ?? []).forEach((jump, jIdx) => {
                if (!jump?.conditions?.length || !isJumpTargetValid(jump.target, slideIds)) return;
                const c = jump.conditions[0];
                const count = traffic ? traffic.jumpTraversals.get(`${slide.id}:${jIdx}`) ?? 0 : undefined;
                const base = `${c?.value !== '' && c?.value != null ? `= “${c.value}”` : c?.comparison?.toLowerCase().replace(/_/g, ' ') ?? ''}${jump.conditions.length > 1 ? ` +${jump.conditions.length - 1}` : ''}`;
                const targetId = jump.target === JUMP_TARGET_SUBMIT ? '__end__' : jump.target;
                const targetClearlyRight = posOf(targetId).x > posOf(slide.id).x + NODE_W * 0.75;
                edges.push({
                    id: `jump-${slide.id}-${jIdx}`,
                    source: slide.id,
                    target: targetId,
                    sourceHandle: 'jump-out',
                    targetHandle: targetClearlyRight ? 'jump-in' : 'jump-in-right',
                    pathOptions: { curvature: 0.45 },
                    label: count !== undefined ? `${base} · ${count}` : base,
                    data: { slideId: slide.id, slideIndex: sIdx, jumpIndex: jIdx },
                    deletable: true,
                    style: { stroke: JUMP_COLOR, strokeWidth: count ? Math.min(1.75 + (3 * count) / Math.max(traffic!.total, 1), 4.75) : 1.75 },
                    labelStyle: { fill: JUMP_COLOR, fontSize: 11, fontWeight: 600 },
                    labelBgStyle: { fill: '#ffffff', stroke: '#c7dcfd' },
                    labelBgPadding: [6, 3] as [number, number],
                    labelBgBorderRadius: 6,
                    markerEnd: { type: MarkerType.ArrowClosed, color: JUMP_COLOR, width: 18, height: 18 }
                });
            });
        });
        return edges;
    }, [slides, slideIds, traffic]);

    const [nodes, setNodes, onNodesChange] = useNodesState(buildNodes());
    const [edges, setEdges, onEdgesChange] = useEdgesState(buildEdges());

    // Re-derive whenever the form model changes (pages/jumps/positions/labels).
    const modelSignature = useMemo(
        () =>
            JSON.stringify(
                slides.map((s, i) => [s.id, pageLabel(s, i), s.properties?.fields?.length, s.properties?.position, s.properties?.jumps, s.properties?.fields?.map((f) => !!f.properties?.logic)])
            ),
        [slides]
    );
    useEffect(() => {
        setNodes(buildNodes());
        setEdges(buildEdges());
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [modelSignature, traffic]);

    /* ------------------------------ actions ------------------------------ */

    const selectSlide = (slideId: string | null) => {
        setSelectedId(slideId);
        const idx = slides.findIndex((s) => s.id === slideId);
        // Keep the builder's active slide in sync so PageJumpEditor edits the right page.
        if (idx >= 0) setActiveSlideComponent({ id: slideId!, index: idx });
    };

    const openPageEditor = (slideId: string) => {
        selectSlide(slideId);
        setActiveFieldComponent(null);
        setOverlayId(slideId);
    };

    const onConnect = useCallback(
        (conn: Connection) => {
            if (conn.sourceHandle !== 'jump-out' || conn.targetHandle !== 'jump-in') return;
            if (!conn.source || !conn.target || conn.source === conn.target) return;
            const sIdx = slides.findIndex((s) => s.id === conn.source);
            if (sIdx < 0) return;
            const target = conn.target === '__end__' ? JUMP_TARGET_SUBMIT : conn.target;
            const jumps = ((slides[sIdx].properties?.jumps as PageJump[] | undefined) ?? []).slice();
            if (jumps.some((j) => j.target === target && !j.conditions?.length)) return; // avoid stacking empty duplicates
            const sources = buildSourceFields(slides, (_sl, i, f) => i <= sIdx && V2InputFields.includes(f.type));
            jumps.push({ operator: LogicalOperator.AND, conditions: [newConditionFor(sources)], target });
            updateSlideJumps(sIdx, jumps);
            // Open the panel on the source page so the creator completes the condition.
            selectSlide(conn.source);
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [slides]
    );

    const onEdgesDelete = useCallback(
        (deleted: Edge[]) => {
            // Group removed jump indexes per slide, then filter each slide's jumps once.
            const bySlide = new Map<number, Set<number>>();
            deleted.forEach((e) => {
                const d = e.data as { slideIndex?: number; jumpIndex?: number } | undefined;
                if (d?.slideIndex === undefined || d?.jumpIndex === undefined) return;
                if (!bySlide.has(d.slideIndex)) bySlide.set(d.slideIndex, new Set());
                bySlide.get(d.slideIndex)!.add(d.jumpIndex);
            });
            bySlide.forEach((jumpIdxs, slideIndex) => {
                const jumps = ((slides[slideIndex]?.properties?.jumps as PageJump[] | undefined) ?? []).filter((_, i) => !jumpIdxs.has(i));
                updateSlideJumps(slideIndex, jumps.length ? jumps : undefined);
            });
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [slides]
    );

    const addPage = () => {
        const id = v4();
        addSlide(
            {
                id,
                index: slides.length,
                type: FieldTypes.SLIDE,
                properties: { layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND, fields: [] }
            },
            slides.length
        );
        setSelectedId(id);
    };

    return (
        <div className="relative flex h-full w-full flex-col bg-white">
            {/* header */}
            <div className="border-b-black-200 flex items-center justify-between border-b px-6 py-3">
                <div>
                    <div className="text-black-900 text-base font-semibold">Flow</div>
                    <div className="text-black-500 text-xs">Drag between the blue dots to branch. Select a page to edit its rules.</div>
                </div>
                <div className="flex items-center gap-2">
                    {showInsights && !insightsLoading && traffic?.total === 0 && <span className="text-black-500 mr-1 text-xs">No responses yet</span>}
                    <button
                        onClick={() => setShowInsights((v) => !v)}
                        title="Overlay how submitted responses travelled each branch"
                        className={
                            'flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs font-medium ' +
                            (showInsights ? 'border-brand-500 bg-brand-100 text-brand-600' : 'border-black-300 text-black-700 hover:border-brand-500 hover:text-brand-600')
                        }
                    >
                        <BarChart3 className="h-3.5 w-3.5" /> {insightsLoading ? 'Loading…' : 'Insights'}
                    </button>
                    <button onClick={addPage} className="border-black-300 text-black-700 hover:border-brand-500 hover:text-brand-600 flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs font-medium">
                        <Plus className="h-3.5 w-3.5" /> Add page
                    </button>
                    <button onClick={() => clearSlidePositions()} title="Reset the layout" className="border-black-300 text-black-700 hover:border-brand-500 hover:text-brand-600 flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs font-medium">
                        <LayoutGrid className="h-3.5 w-3.5" /> Auto-arrange
                    </button>
                    <button aria-label="Close flow view" onClick={onClose} className="text-black-500 hover:text-black-900 ml-2 rounded-md p-1">
                        <X className="h-5 w-5" />
                    </button>
                </div>
            </div>

            <div className="flex min-h-0 flex-1">
                {/* canvas */}
                <div className="h-full min-w-0 flex-1">
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        nodeTypes={nodeTypes}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        onEdgesDelete={onEdgesDelete}
                        onNodeClick={(_, node) => selectSlide(node.type === 'page' ? node.id : null)}
                        onNodeDoubleClick={(_, node) => {
                            if (node.type === 'page') openPageEditor(node.id);
                        }}
                        onEdgeClick={(_, edge) => {
                            const slideId = (edge.data as { slideId?: string } | undefined)?.slideId;
                            if (slideId) selectSlide(slideId);
                        }}
                        onNodeDragStop={(_, node) => {
                            const idx = slides.findIndex((s) => s.id === node.id);
                            if (idx >= 0) updateSlidePosition(idx, { x: node.position.x, y: node.position.y });
                        }}
                        onPaneClick={() => setSelectedId(null)}
                        fitView
                        fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
                        proOptions={{ hideAttribution: false }}
                        deleteKeyCode={['Backspace', 'Delete']}
                    >
                        <Background variant={BackgroundVariant.Dots} gap={22} size={1.5} color="#d6dce8" />
                        <Controls showInteractive={false} />
                        <MiniMap pannable zoomable nodeColor={() => '#dbe4f2'} />
                    </ReactFlow>
                </div>

                {/* side panel */}
                <div className="border-l-black-200 flex h-full w-[340px] shrink-0 flex-col overflow-y-auto border-l bg-white">
                    {selectedSlide ? (
                        <>
                            <div className="border-b-black-200 flex flex-col gap-2 border-b px-4 py-4">
                                <div>
                                    <div className="text-black-400 text-[10px] font-semibold uppercase tracking-wide">Page {selectedIndex + 1}</div>
                                    <div className="text-black-900 truncate text-sm font-semibold">{pageLabel(selectedSlide, selectedIndex).replace(/^Page \d+ · /, '') || 'Untitled page'}</div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <button onClick={() => openPageEditor(selectedSlide.id)} className="bg-brand-500 hover:bg-brand-600 flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium text-white">
                                        <PencilLine className="h-3.5 w-3.5" /> Edit content
                                    </button>
                                    <button
                                        onClick={() => {
                                            const newId = duplicateSlide(selectedIndex);
                                            if (newId) setSelectedId(newId);
                                        }}
                                        className="border-black-300 text-black-700 hover:border-brand-500 flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs font-medium"
                                    >
                                        <Copy className="h-3.5 w-3.5" /> Duplicate
                                    </button>
                                    <button
                                        onClick={() => {
                                            deleteSlide(selectedIndex);
                                            setSelectedId(null);
                                        }}
                                        className="ml-auto flex items-center gap-1 rounded-md border border-red-200 px-2.5 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
                                    >
                                        <Trash2 className="h-3.5 w-3.5" /> Delete
                                    </button>
                                </div>
                            </div>
                            {/* The existing jump editor operates on the builder-active slide, which selectSlide keeps in sync. */}
                            <PageJumpEditor />
                        </>
                    ) : (
                        <div className="text-black-500 flex h-full flex-col items-center justify-center gap-2 px-8 text-center text-xs">
                            <span className="text-black-700 text-sm font-medium">Nothing selected</span>
                            Select a page to edit its branching rules, or drag from a blue dot to another page to create a jump.
                        </div>
                    )}
                </div>
            </div>

            {/* Page-editor overlay — edit content without leaving the flow */}
            {overlaySlide && (
                <div className="absolute inset-0 z-30 flex flex-col bg-black/40 p-5" onClick={() => setOverlayId(null)}>
                    <div className="flex min-h-0 flex-1 overflow-hidden rounded-xl bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
                        <div className="bg-new-white-200 relative flex min-w-0 flex-1 flex-col overflow-hidden">
                            <div className="border-b-black-200 flex items-center justify-between border-b bg-white px-4 py-2.5">
                                <div className="text-black-800 text-sm font-semibold">
                                    Page {overlayIndex + 1} · <span className="text-black-500 font-normal">changes save automatically</span>
                                </div>
                                <button onClick={() => setOverlayId(null)} className="border-black-300 text-black-700 hover:border-brand-500 hover:text-brand-600 flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium">
                                    <X className="h-3.5 w-3.5" /> Back to flow
                                </button>
                            </div>
                            <div className="flex min-h-0 flex-1 items-start justify-center overflow-auto p-6">
                                <div className="!shadow-slide aspect-video overflow-hidden" style={overlayScaleStyle}>
                                    <SlideBuilder slide={overlaySlide} />
                                </div>
                            </div>
                        </div>
                        <div className="border-l-black-200 w-[280px] shrink-0 overflow-y-auto border-l bg-white">
                            <PropertiesDrawer />
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

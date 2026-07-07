'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { FieldTypes, V2InputFields } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { JUMP_TARGET_SUBMIT, LogicalOperator, PageJump } from '@app/models/types/form-builder-shared';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useGetFlowAnalyticsQuery } from '@app/store/redux/form-api';
import { useGetFormAllSubmissionsQuery } from '@app/store/workspaces/api';
import { computeFlowTraffic, fieldHasLogic, FlowTraffic, isJumpTargetValid } from '@app/utils/conditional-logic';
import { buildSourceFields, fieldText, newConditionFor, pageLabel } from '@app/views/molecules/form-builder/condition-editor-shared';
import { ToastAction } from '@app/shadcn/components/ui/toast';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAutosaveStatus } from '@app/store/jotai/autosave-status';
import PageJumpEditor from '@app/views/molecules/form-builder/page-jump-editor';
import PropertiesDrawer from '@app/views/organism/form-builder/properties-drawer';
import SlideBuilder from '@app/views/organism/form-builder/slide-builder';
import { AlertTriangle, BarChart3, Copy, LayoutGrid, PencilLine, Plus, Trash2, X } from 'lucide-react';
import { v4 } from 'uuid';

import { Background, BackgroundVariant, BaseEdge, Connection, Controls, Edge, EdgeLabelRenderer, EdgeProps, Handle, MarkerType, MiniMap, Node, NodeProps, Position, ReactFlow, useEdgesState, useNodesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// Deterministic default layout (used when a page has no saved position).
const NODE_W = 300;
const NODE_H = 96;
const GAP_Y = 72;
const COL_X = 120;
const JUMP_COLOR = '#2456CC';
const NEXT_COLOR = '#c2cad9';

const defaultPos = (k: number) => ({ x: COL_X, y: 40 + k * (NODE_H + GAP_Y) });

/* ----------------------------- custom nodes ------------------------------ */

// Dot styling for the click-to-connect flow: armed dots swell and glow.
// The transparent border is a hit-area extender: at fit zoom the visual dot
// shrinks to ~7px on screen — too small a Fitts target for the view's primary
// gesture — so the clickable box is roughly double the visible dot.
const dotStyle = (isArmed: boolean): React.CSSProperties => ({
    background: JUMP_COLOR,
    backgroundClip: 'padding-box',
    border: '6px solid transparent',
    width: isArmed ? 28 : 24,
    height: isArmed ? 28 : 24,
    cursor: 'pointer',
    boxShadow: isArmed ? '0 0 0 5px rgba(36,86,204,0.25)' : undefined,
    transition: 'all 120ms ease'
});

/** Keyboard parity for the interactive connect dots (Enter/Space = click). */
const dotKeyDown = (handler: () => void) => (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        e.stopPropagation();
        handler();
    }
};

function PageNode({ id, data, selected }: NodeProps<Node<any>>) {
    return (
        <div
            aria-label={`Page ${data.pageNumber}: ${data.label} — ${data.questionCount} question${data.questionCount === 1 ? '' : 's'}`}
            className={'flex w-[300px] flex-col gap-1 rounded-xl border bg-white px-4 py-3 shadow-sm transition-shadow ' + (selected ? 'border-brand-500 shadow-bubble' : 'border-black-200 hover:border-brand-300')}
        >
            <Handle id="next-in" type="target" position={Position.Top} isConnectable={false} style={{ opacity: 0 }} />
            <Handle
                id="jump-in"
                type="target"
                position={Position.Left}
                role="button"
                tabIndex={0}
                aria-label={`Create a jump into page ${data.pageNumber}`}
                style={dotStyle(data.armedMode === 'into')}
                onClick={(e) => {
                    e.stopPropagation();
                    data.onDotClick?.(id, 'in');
                }}
                onKeyDown={dotKeyDown(() => data.onDotClick?.(id, 'in'))}
            />
            {/* Invisible right-side anchor: edges from pages in the same column enter
                here so they bow beside the column instead of crossing it. Users still
                drop connections on the visible left dot. */}
            <Handle id="jump-in-right" type="target" position={Position.Right} isConnectable={false} style={{ opacity: 0, top: '35%' }} />
            <span className="text-black-600 text-[10px] font-semibold uppercase tracking-wide">Page {data.pageNumber}</span>
            <span className="text-black-900 truncate text-sm font-semibold">{data.label}</span>
            {data.questions?.length > 0 && (
                <div className="flex flex-col gap-0.5">
                    {data.questions.map((q: string, i: number) => (
                        <span key={i} className="text-black-600 truncate text-[11px]">
                            · {q}
                        </span>
                    ))}
                    {data.questionCount > data.questions.length && <span className="text-black-600 text-[11px]">+{data.questionCount - data.questions.length} more</span>}
                </div>
            )}
            <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                <span className="text-black-600">
                    {data.questionCount} question{data.questionCount === 1 ? '' : 's'}
                </span>
                {data.showHideCount > 0 && <span className="text-brand-600 bg-brand-100 rounded px-1.5 py-[1px] font-medium">{data.showHideCount} show/hide</span>}
                {data.questionCount === 0 && (
                    <span className="inline-flex items-center gap-0.5 rounded bg-[#FBF3E4] px-1.5 py-[1px] font-medium text-[#B26B00]" title="Responders will see a blank page — add a question or delete it">
                        <AlertTriangle className="h-3 w-3" /> empty page
                    </span>
                )}
                {data.brokenCount > 0 && (
                    <span className="inline-flex items-center gap-0.5 rounded bg-[#FBEFEF] px-1.5 py-[1px] font-medium text-[#C43D3D]">
                        <AlertTriangle className="h-3 w-3" /> broken jump
                    </span>
                )}
                {data.visits !== undefined && (
                    <span className="text-black-700 bg-black-100 rounded px-1.5 py-[1px] font-semibold" title="Submissions whose path visited this page">
                        {data.visits}/{data.totalResponses} visited
                    </span>
                )}
                {data.dropOffs > 0 && (
                    <span className="rounded bg-[#FBF3E4] px-1.5 py-[1px] font-semibold text-[#B26B00]" title="Responders whose last activity was on this page — they never submitted">
                        {data.dropOffs} dropped here
                    </span>
                )}
            </div>
            <Handle
                id="jump-out"
                type="source"
                position={Position.Right}
                role="button"
                tabIndex={0}
                aria-label={`Create a jump from page ${data.pageNumber}`}
                style={dotStyle(data.armedMode === 'from')}
                onClick={(e) => {
                    e.stopPropagation();
                    data.onDotClick?.(id, 'out');
                }}
                onKeyDown={dotKeyDown(() => data.onDotClick?.(id, 'out'))}
            />
            <Handle id="next-out" type="source" position={Position.Bottom} isConnectable={false} style={{ opacity: 0 }} />
        </div>
    );
}

function TerminalNode({ id, data }: NodeProps<Node<any>>) {
    const isEnd = data.kind === 'end';
    return (
        <div className="bg-new-white-200 border-black-200 text-black-600 flex w-[300px] flex-col gap-0.5 rounded-xl border px-4 py-3">
            {isEnd && <Handle id="next-in" type="target" position={Position.Top} isConnectable={false} style={{ opacity: 0 }} />}
            {isEnd && (
                <Handle
                    id="jump-in"
                    type="target"
                    position={Position.Left}
                    role="button"
                    tabIndex={0}
                    aria-label="Create a jump straight to submit"
                    style={dotStyle(data.armedMode === 'into')}
                    onClick={(e) => {
                        e.stopPropagation();
                        data.onDotClick?.(id, 'in');
                    }}
                    onKeyDown={dotKeyDown(() => data.onDotClick?.(id, 'in'))}
                />
            )}
            {isEnd && <Handle id="jump-in-right" type="target" position={Position.Right} isConnectable={false} style={{ opacity: 0, top: '35%' }} />}
            <span className="text-black-600 text-[10px] font-semibold uppercase tracking-wide">{isEnd ? 'End' : 'Start'}</span>
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

/**
 * Right-side bracket edge: both endpoints sit on node right edges, so the
 * default bezier flattens into a rail that grazes the pages in between. This
 * draws an explicit outward arc — the bulge grows gently with the vertical
 * span, guaranteeing daylight between the edge and the column.
 */
function BracketEdge({ id, sourceX, sourceY, targetX, targetY, style, markerEnd, label }: EdgeProps) {
    const bulge = 64 + Math.min(Math.abs(targetY - sourceY) * 0.14, 96);
    const path = `M ${sourceX} ${sourceY} C ${sourceX + bulge} ${sourceY}, ${targetX + bulge} ${targetY}, ${targetX} ${targetY}`;
    // Cubic midpoint (t = 0.5): x = (P0x + 3·P1x + 3·P2x + P3x) / 8
    const labelX = (sourceX + targetX) / 2 + bulge * 0.75;
    const labelY = (sourceY + targetY) / 2;
    return (
        <>
            <BaseEdge id={id} path={path} style={style} markerEnd={markerEnd} />
            {label != null && label !== '' && (
                <EdgeLabelRenderer>
                    <div
                        className="nodrag nopan pointer-events-none absolute rounded-md border bg-white px-1.5 py-0.5 text-[11px] font-semibold"
                        style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`, color: JUMP_COLOR, borderColor: '#C7D7F5' }}
                    >
                        {label}
                    </div>
                </EdgeLabelRenderer>
            )}
        </>
    );
}

const edgeTypes = { bracket: BracketEdge };

/* ------------------------------- flow view ------------------------------- */

export default function FlowView({ onClose }: { onClose?: () => void }) {
    const { formFields, addSlide, deleteSlide, duplicateSlide, updateSlideJumps, updateSlidePosition, clearSlidePositions } = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { toast } = useToast();
    const { autosaveStatus } = useAutosaveStatus();

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
    // Anonymous navigation events → where responders went dark (drop-off).
    const { data: flowAnalytics } = useGetFlowAnalyticsQuery({ workspaceId: workspace?.id, formId: standardForm?.formId } as any, {
        skip: !showInsights || !workspace?.id || !standardForm?.formId
    });
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const selectedIndex = slides.findIndex((s) => s.id === selectedId);
    const selectedSlide = selectedIndex >= 0 ? slides[selectedIndex] : undefined;

    // Click-to-connect: click a right dot to start a jump FROM that page (then
    // click any destination node), or a left dot to start one INTO it (then
    // click the source page). Esc or clicking empty canvas cancels. The handler
    // lives in a ref so node data can stay referentially simple.
    const [armed, setArmed] = useState<{ mode: 'from' | 'into'; id: string } | null>(null);
    const dotClickRef = useRef<(nodeId: string, side: 'in' | 'out') => void>(() => {});

    // Page-editor overlay (double-click / "Edit content") — edit a page without
    // leaving the flow. Reuses the builder's SlideBuilder + PropertiesDrawer.
    const [overlayId, setOverlayId] = useState<string | null>(null);
    const overlayIndex = slides.findIndex((s) => s.id === overlayId);
    const overlaySlide = overlayIndex >= 0 ? slides[overlayIndex] : undefined;

    // Same measured-scale approach as the main editor: the slide lays out at
    // its true 1440×810 design size and is scaled to fit the overlay's mat,
    // with the wrapper sized to the visual card so centring is exact. (The
    // old window-arithmetic version left the sheet off-centre in dead space.)
    const SLIDE_W = 1440;
    const SLIDE_H = 810;
    const overlayMatRef = useRef<HTMLDivElement>(null);
    const [overlayScale, setOverlayScale] = useState(0.5);
    useEffect(() => {
        const mat = overlayMatRef.current;
        if (!mat) return;
        const compute = () => {
            const cs = getComputedStyle(mat);
            const availableWidth = mat.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
            const availableHeight = mat.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
            setOverlayScale(Math.min(availableWidth / SLIDE_W, availableHeight / SLIDE_H, 1));
        };
        compute();
        const observer = new ResizeObserver(compute);
        observer.observe(mat);
        return () => observer.disconnect();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [overlayId]);

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
                totalResponses: traffic?.total,
                dropOffs: showInsights ? flowAnalytics?.dropOffs?.[slide.id] ?? 0 : undefined,
                armedMode: armed?.id === slide.id ? armed.mode : undefined,
                onDotClick: (nid: string, side: 'in' | 'out') => dotClickRef.current?.(nid, side)
            }
        }));
        return [
            { id: '__welcome__', type: 'terminal', position: defaultPos(0), data: { kind: 'welcome', label: 'Welcome', totalResponses: traffic?.total }, deletable: false },
            ...pageNodes.map((n) => ({ ...n, deletable: false })), // deletion goes through the panel (with cleanup), not the Delete key
            {
                id: '__end__',
                type: 'terminal',
                position: defaultPos(slides.length + 1),
                data: { kind: 'end', label: 'Thank you', totalResponses: traffic?.total, armedMode: armed?.id === '__end__' ? armed.mode : undefined, onDotClick: (nid: string, side: 'in' | 'out') => dotClickRef.current?.(nid, side) },
                deletable: false
            }
        ];
    }, [slides, slideIds, traffic, armed, flowAnalytics, showInsights]);

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
                labelStyle: { fill: '#657085', fontSize: 11, fontWeight: 600 },
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
                    type: targetClearlyRight ? undefined : 'bracket',
                    source: slide.id,
                    target: targetId,
                    sourceHandle: 'jump-out',
                    targetHandle: targetClearlyRight ? 'jump-in' : 'jump-in-right',
                    label: count !== undefined ? `${base} · ${count}` : base,
                    data: { slideId: slide.id, slideIndex: sIdx, jumpIndex: jIdx },
                    deletable: true,
                    style: { stroke: JUMP_COLOR, strokeWidth: count ? Math.min(1.75 + (3 * count) / Math.max(traffic!.total, 1), 4.75) : 1.75 },
                    labelStyle: { fill: JUMP_COLOR, fontSize: 11, fontWeight: 600 },
                    labelBgStyle: { fill: '#ffffff', stroke: '#C7D7F5' },
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
        // Edges one frame later: React Flow silently DROPS edges whose source/
        // target handles aren't mounted yet, and same-tick node+edge updates
        // intermittently lose that race — leaving the whole graph unlinked
        // until something else touches the edges array.
        const frame = requestAnimationFrame(() => setEdges(buildEdges()));
        return () => cancelAnimationFrame(frame);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [modelSignature, traffic, armed, flowAnalytics, showInsights]);

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

    // Shared by drag-to-connect and click-to-connect.
    const createJump = useCallback(
        (sourceId: string, rawTargetId: string) => {
            if (!sourceId || !rawTargetId || sourceId === rawTargetId) return;
            const sIdx = slides.findIndex((s) => s.id === sourceId);
            if (sIdx < 0) return;
            const target = rawTargetId === '__end__' ? JUMP_TARGET_SUBMIT : rawTargetId;
            if (target !== JUMP_TARGET_SUBMIT && !slides.some((s) => s.id === target)) return;
            const jumps = ((slides[sIdx].properties?.jumps as PageJump[] | undefined) ?? []).slice();
            if (jumps.some((j) => j.target === target && !j.conditions?.length)) return; // avoid stacking empty duplicates
            const sources = buildSourceFields(slides, (_sl, i, f) => i <= sIdx && V2InputFields.includes(f.type));
            jumps.push({ operator: LogicalOperator.AND, conditions: [newConditionFor(sources)], target });
            updateSlideJumps(sIdx, jumps);
            // Open the panel on the source page so the creator completes the condition.
            selectSlide(sourceId);
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [slides]
    );

    const onConnect = useCallback(
        (conn: Connection) => {
            if (conn.sourceHandle !== 'jump-out' || conn.targetHandle !== 'jump-in') return;
            if (conn.source && conn.target) createJump(conn.source, conn.target);
        },
        [createJump]
    );

    dotClickRef.current = (nodeId, side) => {
        if (side === 'out') {
            if (armed?.mode === 'into' && armed.id !== nodeId) {
                createJump(nodeId, armed.id);
                setArmed(null);
                return;
            }
            setArmed(armed?.mode === 'from' && armed.id === nodeId ? null : { mode: 'from', id: nodeId });
        } else {
            if (armed?.mode === 'from' && armed.id !== nodeId) {
                createJump(armed.id, nodeId);
                setArmed(null);
                return;
            }
            setArmed(armed?.mode === 'into' && armed.id === nodeId ? null : { mode: 'into', id: nodeId });
        }
    };
    useEffect(() => {
        if (!armed) return;
        const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setArmed(null);
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [armed]);

    // Escape closes the page-editor overlay (matching the backdrop click).
    useEffect(() => {
        if (!overlayId) return;
        const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOverlayId(null);
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [overlayId]);
    const armedName = armed ? (armed.id === '__end__' ? 'Submit' : `Page ${(slides.findIndex((s) => s.id === armed.id) ?? 0) + 1}`) : null;

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
            if (!bySlide.size) return;
            // Snapshot before removal — a jump can carry several conditions, so a
            // keystroke shouldn't silently discard work that took time to build.
            const removedRules: Array<{ slideIndex: number; jumps: PageJump[] }> = [];
            bySlide.forEach((jumpIdxs, slideIndex) => {
                const before = (slides[slideIndex]?.properties?.jumps as PageJump[] | undefined) ?? [];
                removedRules.push({ slideIndex, jumps: before.filter((_, i) => jumpIdxs.has(i)) });
                const jumps = before.filter((_, i) => !jumpIdxs.has(i));
                updateSlideJumps(slideIndex, jumps.length ? jumps : undefined);
            });
            const removedCount = removedRules.reduce((n, r) => n + r.jumps.length, 0);
            toast({
                description: `${removedCount === 1 ? 'Jump rule' : `${removedCount} jump rules`} removed`,
                duration: 8000,
                action: (
                    <ToastAction
                        altText="Undo removing the jump"
                        onClick={() => {
                            removedRules.forEach(({ slideIndex, jumps }) => {
                                const current = ((slides[slideIndex]?.properties?.jumps as PageJump[] | undefined) ?? []).slice();
                                updateSlideJumps(slideIndex, [...current, ...jumps]);
                            });
                        }}
                    >
                        Undo
                    </ToastAction>
                )
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
                    {/* aria-live: screen readers announce entering/leaving connect mode */}
                    <div aria-live="polite">
                        {armed ? (
                            <div className="text-brand-600 text-xs font-medium">
                                {armed.mode === 'from' ? `Creating a jump from ${armedName} — click the destination page` : `Creating a jump into ${armedName} — click the source page`} · Esc to cancel
                            </div>
                        ) : (
                            <div className="text-black-600 text-xs">Click or drag a blue dot to branch. Select a page to edit its rules.</div>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {/* The navbar's save indicator is hidden while Flow is fullscreen —
                        carry the same reassurance here. */}
                    {autosaveStatus.state !== 'idle' && (
                        <span aria-live="polite" className={'mr-1 whitespace-nowrap text-xs font-medium ' + (autosaveStatus.state === 'error' ? 'text-[#B26B00]' : 'text-black-600')}>
                            {autosaveStatus.state === 'saving' && 'Saving…'}
                            {autosaveStatus.state === 'saved' && 'Saved'}
                            {autosaveStatus.state === 'error' && "Couldn't save — edit to retry"}
                        </span>
                    )}
                    {/* Two instruments, labelled apart: node/edge counts replay the
                        SUBMITTED responses (all-time), while journey tracking counts
                        anonymous page-to-page sessions — including people who never
                        submitted, and only since flow analytics was enabled. Shown
                        unlabelled they read as the same number disagreeing. */}
                    {showInsights && (traffic?.total ?? 0) > 0 && (
                        <span className="text-black-600 mr-1 text-xs" title="All-time submitted responses — the population behind the node and edge counts">
                            <span className="font-semibold">{traffic!.total}</span> response{traffic!.total === 1 ? '' : 's'}
                        </span>
                    )}
                    {showInsights && flowAnalytics && flowAnalytics.totalSessions > 0 && (
                        <span className="text-black-600 mr-1 text-xs" title="Anonymous page-to-page journeys since flow analytics was enabled — includes visitors who never submitted, which is where the drop-off chips come from">
                            · journeys: {flowAnalytics.totalSessions} started · {flowAnalytics.submittedSessions} finished
                        </span>
                    )}
                    {showInsights && !insightsLoading && traffic?.total === 0 && (!flowAnalytics || flowAnalytics.totalSessions === 0) && <span className="text-black-500 mr-1 text-xs">No responses yet</span>}
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
                        edgeTypes={edgeTypes}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        onEdgesDelete={onEdgesDelete}
                        onNodeClick={(_, node) => {
                            if (armed) {
                                // Complete the click-to-connect on any valid node body.
                                if (armed.mode === 'from' && node.id !== armed.id && (node.type === 'page' || node.id === '__end__')) createJump(armed.id, node.id);
                                else if (armed.mode === 'into' && node.type === 'page' && node.id !== armed.id) createJump(node.id, armed.id);
                                setArmed(null);
                                return;
                            }
                            selectSlide(node.type === 'page' ? node.id : null);
                        }}
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
                        onPaneClick={() => {
                            setSelectedId(null);
                            setArmed(null);
                        }}
                        fitView
                        fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
                        // Re-fit once node heights are actually measured — the mount-time
                        // fitView uses estimated sizes, which left the Start node clipped
                        // under the header on open.
                        onInit={(instance) => {
                            window.requestAnimationFrame(() => instance.fitView({ padding: 0.2, maxZoom: 1 }));
                        }}
                        proOptions={{ hideAttribution: false }}
                        deleteKeyCode={['Backspace', 'Delete']}
                        connectOnClick={false}
                    >
                        <Background variant={BackgroundVariant.Dots} gap={22} size={1.5} color="#d6dce8" />
                        <Controls showInteractive={false} />
                        {/* A minimap earns its canvas space only once the graph outgrows
                            the viewport — for a handful of nodes it reads as a broken
                            placeholder box. */}
                        {nodes.length > 8 && <MiniMap pannable zoomable className="!h-[110px] !w-[150px]" nodeColor={() => '#CBD5E6'} maskColor="rgba(233, 238, 245, 0.65)" />}
                    </ReactFlow>
                </div>

                {/* side panel */}
                <div className="border-l-black-200 flex h-full w-[340px] shrink-0 flex-col overflow-y-auto border-l bg-white">
                    {selectedSlide ? (
                        <>
                            <div className="border-b-black-200 flex flex-col gap-2 border-b px-4 py-4">
                                <div>
                                    <div className="text-black-600 text-[10px] font-semibold uppercase tracking-wide">Page {selectedIndex + 1}</div>
                                    {/* The canvas card may truncate the question; the panel is
                                        where the full text belongs — wrap, don't clip. */}
                                    <div className="text-black-900 break-words text-sm font-semibold leading-snug">{pageLabel(selectedSlide, selectedIndex).replace(/^Page \d+ · /, '') || 'Untitled page'}</div>
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
                                        className="ml-auto flex items-center gap-1 rounded-md border border-[#EFD2D2] px-2.5 py-1.5 text-xs font-medium text-[#C43D3D] hover:bg-[#FBEFEF]"
                                    >
                                        <Trash2 className="h-3.5 w-3.5" /> Delete
                                    </button>
                                </div>
                            </div>
                            {/* The existing jump editor operates on the builder-active slide, which selectSlide keeps in sync. */}
                            <PageJumpEditor />
                        </>
                    ) : (
                        <div className="text-black-600 flex h-full flex-col items-center justify-center gap-2 px-8 text-center text-xs">
                            <span className="text-black-700 text-sm font-medium">Nothing selected</span>
                            Select a page to edit its branching rules, or drag from a blue dot to another page to create a jump.
                        </div>
                    )}
                </div>
            </div>

            {/* Page-editor overlay — edit content without leaving the flow */}
            {overlaySlide && (
                <div role="dialog" aria-modal="true" aria-label={`Edit page ${overlayIndex + 1}`} className="absolute inset-0 z-30 flex flex-col bg-black/40 p-5" onClick={() => setOverlayId(null)}>
                    <div className="flex min-h-0 flex-1 overflow-hidden rounded-xl bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
                        <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
                            <div className="border-b-black-200 flex items-center justify-between gap-4 border-b bg-white px-4 py-2.5">
                                <div className="min-w-0">
                                    <div className="text-black-600 text-[10px] font-semibold uppercase tracking-wide">Page {overlayIndex + 1}</div>
                                    <div className="text-black-900 truncate text-sm font-semibold">{pageLabel(overlaySlide, overlayIndex).replace(/^Page \d+ · /, '') || 'Untitled page'}</div>
                                </div>
                                <div className="flex shrink-0 items-center gap-3">
                                    {/* Live save state beats the static "changes save automatically" claim. */}
                                    <span aria-live="polite" className={'whitespace-nowrap text-xs ' + (autosaveStatus.state === 'error' ? 'font-medium text-[#B26B00]' : 'text-black-600')}>
                                        {autosaveStatus.state === 'saving' && 'Saving…'}
                                        {autosaveStatus.state === 'saved' && 'Saved'}
                                        {autosaveStatus.state === 'error' && "Couldn't save — edit to retry"}
                                        {autosaveStatus.state === 'idle' && 'Changes save automatically'}
                                    </span>
                                    <button onClick={() => setOverlayId(null)} className="border-black-300 text-black-700 hover:border-brand-500 hover:text-brand-600 flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs font-medium">
                                        <X className="h-3.5 w-3.5" /> Back to flow
                                    </button>
                                </div>
                            </div>
                            {/* Same mat + floating-sheet treatment as the main canvas, so
                                "edit a page" looks identical wherever it happens. */}
                            <div ref={overlayMatRef} className="flex min-h-0 flex-1 overflow-auto bg-[#E9EEF5] px-8 py-8" onClick={() => setActiveFieldComponent(null)}>
                                <div className="m-auto shrink-0" style={{ width: SLIDE_W * overlayScale, height: SLIDE_H * overlayScale }}>
                                    <div
                                        className="border-black-400 overflow-hidden rounded-lg border bg-white"
                                        style={{
                                            width: SLIDE_W,
                                            height: SLIDE_H,
                                            transform: `scale(${overlayScale})`,
                                            transformOrigin: 'top left',
                                            boxShadow: '0px 1px 3px rgba(16, 24, 38, 0.06), 0px 12px 32px rgba(16, 24, 38, 0.12)'
                                        }}
                                    >
                                        <SlideBuilder slide={overlaySlide} />
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div className="border-l-black-200 w-[300px] shrink-0 overflow-y-auto border-l bg-white">
                            <PropertiesDrawer />
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

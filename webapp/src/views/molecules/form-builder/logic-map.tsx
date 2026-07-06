'use client';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldConditionalLogic, JUMP_TARGET_SUBMIT, LogicCondition, PageJump } from '@app/models/types/form-builder-shared';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { fieldHasLogic, isJumpTargetValid } from '@app/utils/conditional-logic';
import { AlertTriangle, ArrowRight, X } from 'lucide-react';
import { COMPARISON_LABELS, fieldText, pageLabel } from './condition-editor-shared';

// Fixed geometry so page positions (and therefore the edge paths) are deterministic
// without measuring the DOM.
const PAD = 40;
const NODE_W = 320;
const NODE_H = 104;
const GAP = 64;
const RAIL = 210;
const NEXT = '#c2cad9';
const JUMP = '#0764eb';
const BROKEN = '#d92d20';

interface MapNode {
    kind: 'welcome' | 'page' | 'end';
    label: string;
    slide?: StandardFormFieldDto;
    slideIndex?: number;
    top: number;
}

export default function LogicMap({ onClose }: { onClose?: () => void }) {
    const { formFields } = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();

    const slides = formFields || [];
    const slideIds = new Set(slides.map((s) => s.id));

    const nodes: MapNode[] = [
        { kind: 'welcome', label: 'Welcome', top: 0 },
        ...slides.map((slide, i) => ({ kind: 'page' as const, label: pageLabel(slide, i), slide, slideIndex: i, top: 0 })),
        { kind: 'end', label: 'Thank you', top: 0 }
    ];
    nodes.forEach((n, k) => (n.top = PAD + k * (NODE_H + GAP)));

    const centerY = (k: number) => nodes[k].top + NODE_H / 2;
    const nodeIndexForSlide = (slideIndex: number) => slideIndex + 1; // welcome is 0
    const endNodeIndex = nodes.length - 1;
    const targetNodeIndex = (target: string): number => {
        if (target === JUMP_TARGET_SUBMIT) return endNodeIndex;
        const s = slides.findIndex((sl) => sl.id === target);
        return s >= 0 ? nodeIndexForSlide(s) : -1;
    };

    const width = PAD + NODE_W + RAIL + PAD;
    const height = PAD + nodes.length * (NODE_H + GAP) - GAP + PAD;

    const conditionSummary = (jump: PageJump): string => {
        const c: LogicCondition | undefined = jump.conditions?.[0];
        const cmp = c ? COMPARISON_LABELS[c.comparison] ?? 'matches' : 'matches';
        const val = c && c.value !== '' && c.value != null ? ` “${c.value}”` : '';
        const extra = (jump.conditions?.length ?? 0) > 1 ? ` +${(jump.conditions!.length - 1)}` : '';
        return `${cmp}${val}${extra}`;
    };

    const focusPage = (slideIndex: number) => {
        setActiveFieldComponent(null);
        setActiveSlideComponent({ id: slides[slideIndex].id, index: slideIndex });
        onClose?.();
    };

    // Collect edges (valid jumps only draw arcs; broken jumps render inside the node).
    const nextX = PAD + NODE_W / 2;
    const rightX = PAD + NODE_W;

    return (
        <div className="flex h-full w-full flex-col bg-white">
            <div className="border-b-black-200 flex items-center justify-between border-b px-6 py-4">
                <div>
                    <div className="text-black-900 text-base font-semibold">Logic map</div>
                    <div className="text-black-500 text-xs">How answers route people through your form. Select a page to edit its logic.</div>
                </div>
                <div className="flex items-center gap-4">
                    <div className="text-black-500 hidden items-center gap-3 text-[11px] md:flex">
                        <span className="flex items-center gap-1">
                            <span className="h-0.5 w-4 rounded" style={{ background: NEXT }} /> next page
                        </span>
                        <span className="flex items-center gap-1">
                            <span className="h-0.5 w-4 rounded" style={{ background: JUMP }} /> jump
                        </span>
                        <span className="flex items-center gap-1">
                            <span className="h-0.5 w-4 rounded" style={{ background: BROKEN }} /> broken
                        </span>
                    </div>
                    <button aria-label="Close logic map" onClick={onClose} className="text-black-500 hover:text-black-900 rounded-md p-1">
                        <X className="h-5 w-5" />
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-auto bg-[#f6f8fb] p-6">
                <div className="relative mx-auto" style={{ width, height }}>
                    <svg width={width} height={height} className="pointer-events-none absolute inset-0">
                        <defs>
                            <marker id="lm-next" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                                <path d="M0 0 L10 5 L0 10 z" fill={NEXT} />
                            </marker>
                            <marker id="lm-jump" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                                <path d="M0 0 L10 5 L0 10 z" fill={JUMP} />
                            </marker>
                        </defs>

                        {/* Linear "next page" spine between consecutive nodes */}
                        {nodes.slice(0, -1).map((n, k) => (
                            <line key={`next-${k}`} x1={nextX} y1={n.top + NODE_H} x2={nextX} y2={nodes[k + 1].top} stroke={NEXT} strokeWidth={1.5} markerEnd="url(#lm-next)" />
                        ))}

                        {/* Jump arcs */}
                        {slides.map((slide, sIdx) => {
                            const jumps = (slide?.properties?.jumps as PageJump[] | undefined)?.filter((j) => isJumpTargetValid(j.target, slideIds)) ?? [];
                            const srcNode = nodeIndexForSlide(sIdx);
                            const n = jumps.length;
                            return jumps.map((jump, j) => {
                                const tgt = targetNodeIndex(jump.target);
                                const sy = centerY(srcNode) + (j - (n - 1) / 2) * 16;
                                const ty = centerY(tgt);
                                const bulge = 44 + Math.min(Math.abs(ty - sy) * 0.28, RAIL - 70);
                                return <path key={`jump-${sIdx}-${j}`} d={`M ${rightX} ${sy} C ${rightX + bulge} ${sy}, ${rightX + bulge} ${ty}, ${rightX + 5} ${ty}`} fill="none" stroke={JUMP} strokeWidth={1.75} markerEnd="url(#lm-jump)" />;
                            });
                        })}
                    </svg>

                    {/* Jump labels (clickable, over the arcs) */}
                    {slides.map((slide, sIdx) => {
                        const jumps = (slide?.properties?.jumps as PageJump[] | undefined)?.filter((j) => isJumpTargetValid(j.target, slideIds)) ?? [];
                        const srcNode = nodeIndexForSlide(sIdx);
                        const n = jumps.length;
                        return jumps.map((jump, j) => {
                            const tgt = targetNodeIndex(jump.target);
                            const sy = centerY(srcNode) + (j - (n - 1) / 2) * 16;
                            const ty = centerY(tgt);
                            const bulge = 44 + Math.min(Math.abs(ty - sy) * 0.28, RAIL - 70);
                            // Anchor the label near its source page (spread by node y) rather than the
                            // arc midpoint, so labels from different pages don't collide.
                            void bulge;
                            return (
                                <button
                                    key={`label-${sIdx}-${j}`}
                                    onClick={() => focusPage(sIdx)}
                                    title="Edit this rule"
                                    className="shadow-tooltip border-brand-200 hover:border-brand-500 absolute z-10 max-w-[180px] truncate rounded-md border bg-white px-2 py-1 text-[11px] font-medium text-brand-600"
                                    style={{ left: rightX + 18, top: sy - 11 }}
                                >
                                    {conditionSummary(jump)}
                                </button>
                            );
                        });
                    })}

                    {/* Nodes */}
                    {nodes.map((node, k) => {
                        const terminal = node.kind !== 'page';
                        const fieldRules = node.slide?.properties?.fields?.filter((f) => fieldHasLogic(f)).length ?? 0;
                        const jumps = (node.slide?.properties?.jumps as PageJump[] | undefined) ?? [];
                        const brokenJumps = jumps.filter((jp) => jp.conditions?.length && !isJumpTargetValid(jp.target, slideIds));
                        const validJumps = jumps.filter((jp) => jp.conditions?.length && isJumpTargetValid(jp.target, slideIds));
                        return (
                            <div
                                key={`node-${k}`}
                                onClick={() => node.kind === 'page' && focusPage(node.slideIndex!)}
                                className={
                                    'absolute flex flex-col justify-center gap-1 rounded-xl border px-4 py-3 transition-shadow ' +
                                    (terminal ? 'bg-new-white-200 border-black-200 text-black-600 ' : 'hover:border-brand-500 hover:shadow-bubble cursor-pointer border-black-200 bg-white ')
                                }
                                style={{ left: PAD, top: node.top, width: NODE_W, height: NODE_H }}
                            >
                                <div className="flex items-center gap-2">
                                    {node.kind === 'welcome' && <span className="text-black-400 text-[10px] font-semibold uppercase tracking-wide">Start</span>}
                                    {node.kind === 'end' && <span className="text-black-400 text-[10px] font-semibold uppercase tracking-wide">End</span>}
                                    {node.kind === 'page' && <span className="text-black-400 text-[10px] font-semibold uppercase tracking-wide">Page {node.slideIndex! + 1}</span>}
                                </div>
                                <div className={'truncate text-sm font-semibold ' + (terminal ? 'text-black-700' : 'text-black-900')}>{node.label}</div>
                                {node.kind === 'page' && (
                                    <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                                        <span className="text-black-500">{node.slide?.properties?.fields?.length ?? 0} question{(node.slide?.properties?.fields?.length ?? 0) === 1 ? '' : 's'}</span>
                                        {fieldRules > 0 && <span className="text-brand-600 bg-brand-100 rounded px-1.5 py-[1px] font-medium">{fieldRules} show/hide</span>}
                                        {validJumps.length > 0 && <span className="text-brand-600 bg-brand-100 rounded px-1.5 py-[1px] font-medium">{validJumps.length} jump{validJumps.length === 1 ? '' : 's'}</span>}
                                        {brokenJumps.map((_, bi) => (
                                            <span key={bi} className="inline-flex items-center gap-0.5 rounded bg-red-50 px-1.5 py-[1px] font-medium text-red-600">
                                                <AlertTriangle className="h-3 w-3" /> broken jump
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>

                {slides.length === 0 && <div className="text-black-500 mt-6 text-center text-sm">Add a page to start mapping your form’s flow.</div>}
            </div>
        </div>
    );
}

import React, { Profiler, ProfilerOnRenderCallback } from 'react';

/**
 * Counts React commits per id through <Profiler>, for performance tests:
 * wrap each component under test in <RenderCounter id="..." counts={counts}>
 * and read `counts.byId` (or `counts.total()`) after an interaction. `reset()`
 * starts a new measurement.
 */
export interface RenderCounts {
    byId: Map<string, number>;
    durations: number[];
    total: () => number;
    rendered: () => string[];
    reset: () => void;
}

export function createRenderCounts(): RenderCounts {
    const counts: RenderCounts = {
        byId: new Map(),
        durations: [],
        total: () => Array.from(counts.byId.values()).reduce((sum, n) => sum + n, 0),
        rendered: () => Array.from(counts.byId.keys()),
        reset: () => {
            counts.byId.clear();
            counts.durations.length = 0;
        }
    };
    return counts;
}

export function RenderCounter({ id, counts, children }: { id: string; counts: RenderCounts; children: React.ReactNode }) {
    const onRender: ProfilerOnRenderCallback = (profilerId, _phase, actualDuration) => {
        counts.byId.set(profilerId, (counts.byId.get(profilerId) ?? 0) + 1);
        counts.durations.push(actualDuration);
    };
    return (
        <Profiler id={id} onRender={onRender}>
            {children}
        </Profiler>
    );
}

// ---------------------------------------------------------------------------
// Which components rendered: a whole tree under one <Profiler>
// ---------------------------------------------------------------------------

/** React fiber tags of components that run a render (function, class, forwardRef, memo, simple memo). */
const COMPONENT_TAGS = new Set([0, 1, 11, 14, 15]);
/** The fiber flag React sets on a component whose render ran in this pass. */
const PERFORMED_WORK = 1;

interface Fiber {
    tag: number;
    key: string | null;
    type: any;
    elementType: any;
    flags: number;
    memoizedProps: any;
    child: Fiber | null;
    sibling: Fiber | null;
    return: Fiber | null;
    alternate: Fiber | null;
    stateNode: any;
}

function fiberName(fiber: Fiber): string {
    const type = fiber.type ?? fiber.elementType;
    if (typeof type === 'function') return type.displayName || type.name || 'Anonymous';
    if (type && typeof type === 'object') {
        const inner = type.type ?? type.render;
        return type.displayName || inner?.displayName || inner?.name || 'Anonymous';
    }
    return String(type);
}

/**
 * Groups rendered components into units: the nearest enclosing component
 * named in `boundaries` names the unit (e.g. `field:<id>` for a canvas
 * question); a component outside every boundary is a unit of its own.
 */
export type UnitBoundaries = Record<string, (props: any) => string>;

export interface RenderedComponent {
    name: string;
    unit: string;
}

export interface ComponentRenders {
    /** Components whose render ran since the last reset (mounts included). */
    rendered: RenderedComponent[];
    /** React commits since the last reset. */
    commits: number;
    /** Distinct units among `rendered`. */
    units: () => string[];
    reset: () => void;
    /** Pass to the <Profiler> around the tree (see ComponentRenderTracker). */
    onCommit: () => void;
}

/**
 * Tracks which components render in a tree rendered into `container`: after
 * each commit it walks the committed tree against the previous one, the way
 * React DevTools does (an untouched subtree is skipped; a component counts
 * when its render ran). Mount the tree inside <ComponentRenderTracker>.
 */
export function trackComponentRenders(container: HTMLElement, boundaries: UnitBoundaries = {}): ComponentRenders {
    const rendered: RenderedComponent[] = [];
    const unitOf = (fiber: Fiber): string => {
        for (let at: Fiber | null = fiber; at; at = at.return) {
            if (!COMPONENT_TAGS.has(at.tag)) continue;
            const boundary = boundaries[fiberName(at)];
            if (boundary) return boundary(at.memoizedProps ?? {});
        }
        return fiberName(fiber);
    };
    const visit = (next: Fiber) => {
        const prev = next.alternate;
        if (COMPONENT_TAGS.has(next.tag) && (prev === null || (next.flags & PERFORMED_WORK) !== 0)) rendered.push({ name: fiberName(next), unit: unitOf(next) });
        if (prev && next.child === prev.child) return;
        for (let child = next.child; child; child = child.sibling) visit(child);
    };
    const tracker: ComponentRenders = {
        rendered,
        commits: 0,
        units: () => Array.from(new Set(rendered.map((entry) => entry.unit))),
        reset: () => {
            rendered.length = 0;
            tracker.commits = 0;
        },
        onCommit: () => {
            const key = Object.keys(container).find((name) => name.startsWith('__reactContainer$'));
            const hostRoot: Fiber | undefined = key ? (container as any)[key] : undefined;
            const current: Fiber | undefined = hostRoot?.stateNode?.current;
            if (!current) return;
            tracker.commits += 1;
            if (current.alternate && current.child === current.alternate.child) return;
            for (let child = current.child; child; child = child.sibling) visit(child);
        }
    };
    return tracker;
}

/** The <Profiler> that hands each commit of `children` to a tracker. */
export function ComponentRenderTracker({ tracker, children }: { tracker: ComponentRenders; children: React.ReactNode }) {
    return (
        <Profiler id="component-render-tracker" onRender={tracker.onCommit}>
            {children}
        </Profiler>
    );
}

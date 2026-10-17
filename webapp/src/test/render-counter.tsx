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

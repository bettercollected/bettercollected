'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';

import DataTable, { TableProps } from 'react-data-table-component';

import { cn } from '@app/shadcn/util/lib';

/**
 * A table that is wider than its card scrolls sideways inside it. Without a cue a phone shows one column and nothing
 * says there are more, so the scroll region shades the edge that has more behind it (the strong hairline colour fading out, CSS
 * only, shown from the scroll position). The region is a named landmark a keyboard can focus (`tabIndex={0}`, `role="region"`,
 * `aria-label`), so the arrow keys scroll it.
 */
export function ScrollRegion({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
    const ref = useRef<HTMLDivElement>(null);
    const [more, setMore] = useState({ start: false, end: false });

    const measure = useCallback(() => {
        const element = ref.current;
        if (!element) return;
        const start = element.scrollLeft > 1;
        const end = element.scrollLeft + element.clientWidth < element.scrollWidth - 1;
        setMore((previous) => (previous.start === start && previous.end === end ? previous : { start, end }));
    }, []);

    useEffect(() => {
        measure();
        const element = ref.current;
        if (!element || typeof ResizeObserver === 'undefined') return;
        const observer = new ResizeObserver(measure);
        observer.observe(element);
        // the table inside grows and shrinks with its rows and columns
        if (element.firstElementChild) observer.observe(element.firstElementChild);
        return () => observer.disconnect();
    }, [measure]);

    const fade = 'pointer-events-none absolute inset-y-0 w-6 opacity-0 transition-opacity duration-150 data-[more=true]:opacity-100';
    return (
        <div className={cn('relative min-w-0', className)}>
            <div ref={ref} role="region" tabIndex={0} aria-label={label} onScroll={measure} className="min-w-0 overflow-x-auto">
                {children}
            </div>
            <span aria-hidden="true" data-fade="start" data-more={more.start} className={cn(fade, 'left-0 bg-linear-to-r from-hairline-strong to-transparent')} />
            <span aria-hidden="true" data-fade="end" data-more={more.end} className={cn(fade, 'right-0 bg-linear-to-l from-hairline-strong to-transparent')} />
        </div>
    );
}

/** The app's data table inside a ScrollRegion: every admin table reads this one wrapper. `label` names the region. */
export default function ScrollTable<T>({ label, ...props }: TableProps<T> & { label: string }) {
    return (
        <ScrollRegion label={label}>
            {/* the table's own scroll box is off: this region is the one that scrolls (and shows the fade) */}
            <DataTable<T> responsive={false} {...props} />
        </ScrollRegion>
    );
}

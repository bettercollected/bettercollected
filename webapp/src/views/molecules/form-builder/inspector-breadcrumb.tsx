'use client';

import { Fragment } from 'react';

import { InspectorLevel } from '@app/lib/hooks/use-inspector-escape';
import { cn } from '@app/shadcn/util/lib';

export interface InspectorCrumb {
    level: InspectorLevel;
    label: string;
}

/**
 * "Form › Page 2 › Question": where the inspector is. Every crumb above the
 * current one is a button that goes to that level; the current one is
 * marked for assistive tech and takes focus when Escape moves up a level.
 */
export default function InspectorBreadcrumb({ crumbs, current, onSelect }: { crumbs: InspectorCrumb[]; current: InspectorLevel; onSelect: (level: InspectorLevel) => void }) {
    return (
        <nav aria-label="Settings location" className="shrink-0 border-b border-black-300 px-4 py-2.5">
            <ol className="flex min-w-0 items-center gap-1 text-xs">
                {crumbs.map((crumb, index) => {
                    const isCurrent = crumb.level === current;
                    return (
                        <Fragment key={crumb.level}>
                            {index > 0 && (
                                <li aria-hidden="true" className="shrink-0 text-black-500 select-none">
                                    ›
                                </li>
                            )}
                            <li className={cn('min-w-0', crumb.level === 'question' ? 'flex-1' : 'shrink-0')}>
                                {isCurrent ? (
                                    <span aria-current="location" tabIndex={-1} data-inspector-current className="block truncate rounded-[2px] px-1 py-0.5 font-semibold text-black-900" title={crumb.label}>
                                        {crumb.label}
                                    </span>
                                ) : (
                                    <button type="button" onClick={() => onSelect(crumb.level)} className="block max-w-full truncate rounded-[2px] px-1 py-0.5 font-medium text-black-600 hover:bg-black-200 hover:text-black-900" title={crumb.label}>
                                        {crumb.label}
                                    </button>
                                )}
                            </li>
                        </Fragment>
                    );
                })}
            </ol>
        </nav>
    );
}

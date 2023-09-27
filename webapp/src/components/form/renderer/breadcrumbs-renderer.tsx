import React from 'react';

import { ChevronRight } from '@mui/icons-material';

import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';

interface BreadcrumbRendererProps {
    items: Array<BreadcrumbsItem>;
}

function BreadcrumbRenderer({ items }: BreadcrumbRendererProps) {
    return (
        <div data-testid="breadcrumbs-renderer" className="overflow-auto h-[56px]">
            <nav className="flex h-full" aria-label="Breadcrumb">
                <ol className="flex items-center">
                    {!!items &&
                        Array.isArray(items) &&
                        items.map((item: BreadcrumbsItem, idx: number) => {
                            const Component = item.disabled ? 'span' : 'a';
                            const props = item.disabled ? {} : { href: item.url };
                            return (
                                <li key={idx} className="inline-flex body4 items-center">
                                    <Component {...props} data-testid={'item' + idx} aria-hidden className={`inline-flex truncate items-center`}>
                                        {item.title}
                                    </Component>
                                    {idx !== items.length - 1 && <ChevronRight className="text-black-600" />}
                                </li>
                            );
                        })}
                </ol>
            </nav>
        </div>
    );
}

export default React.memo(BreadcrumbRenderer);

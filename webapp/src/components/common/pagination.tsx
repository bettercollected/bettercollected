// @ts-nocheck
import React from 'react';
import {
    Pagination,
    PaginationContent,
    PaginationEllipsis,
    PaginationItem,
    PaginationLink,
    PaginationNext,
    PaginationPrevious,
} from "@app/shadcn/components/ui/pagination"

interface PaginationProps {
    count?: number; // total pages (MUI uses 'count' for number of pages)
    page?: number;     // current page
    onChange?: (event: any, page: number) => void;
    className?: string;
    color?: any;
    shape?: any;
    boundaryCount?: number;
    siblingCount?: number;
}

const StyledPagination = ({ count = 1, page = 1, onChange, className }: PaginationProps) => {

    const onPageChange = (newPage: number) => {
        if (newPage >= 1 && newPage <= count && onChange) {
            onChange(null, newPage);
        }
    };

    const renderPageNumbers = () => {
        const items = [];

        // Simplified Logic: Show 1, ... Current-1, Current, Current+1, ... Last
        const siblings = 0;
        const start = Math.max(1, page - siblings);
        const end = Math.min(count, page + siblings);

        // Always show first (1)
        if (start > 1) {
            items.push(
                <PaginationItem key={1}>
                    <PaginationLink
                        href="#"
                        onClick={(e) => { e.preventDefault(); onPageChange(1); }}
                        isActive={page === 1}
                    >
                        1
                    </PaginationLink>
                </PaginationItem>
            );
            if (start > 2) {
                items.push(
                    <PaginationItem key="ellipsis-start">
                        <PaginationEllipsis />
                    </PaginationItem>
                );
            }
        }

        for (let i = start; i <= end; i++) {
            // Avoid duplicate 1 or count if already handled by boundary logic
            if (i === 1 && start > 1) continue; // Already added
            if (i === count && end < count) continue; // Will be added at end

            items.push(
                <PaginationItem key={i}>
                    <PaginationLink
                        href="#"
                        onClick={(e) => { e.preventDefault(); onPageChange(i); }}
                        isActive={page === i}
                    >
                        {i}
                    </PaginationLink>
                </PaginationItem>
            );
        }

        // Always show last (count)
        if (end < count) {
            if (end < count - 1) {
                items.push(
                    <PaginationItem key="ellipsis-end">
                        <PaginationEllipsis />
                    </PaginationItem>
                );
            }
            items.push(
                <PaginationItem key={count}>
                    <PaginationLink
                        href="#"
                        onClick={(e) => { e.preventDefault(); onPageChange(count); }}
                        isActive={page === count}
                    >
                        {count}
                    </PaginationLink>
                </PaginationItem>
            );
        }

        return items;
    };

    if (count <= 1) return null;

    return (
        <Pagination className={className}>
            <PaginationContent>
                <PaginationItem>
                    <PaginationPrevious
                        href="#"
                        onClick={(e) => { e.preventDefault(); onPageChange(page - 1); }}
                        className={page <= 1 ? "pointer-events-none opacity-50" : ""}
                    />
                </PaginationItem>

                {renderPageNumbers()}

                <PaginationItem>
                    <PaginationNext
                        href="#"
                        onClick={(e) => { e.preventDefault(); onPageChange(page + 1); }}
                        className={page >= count ? "pointer-events-none opacity-50" : ""}
                    />
                </PaginationItem>
            </PaginationContent>
        </Pagination>
    );
};

export default StyledPagination;

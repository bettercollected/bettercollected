import Link from 'next/link';

import { useTranslation } from 'react-i18next';

import { responsesListLocale as text } from '@app/constants/locales/responses-list';
import { cn } from '@app/shadcn/util/lib';
import { PAGE_SIZES, PageSize, nearbyPages } from '@app/utils/response-list-state';

interface Props {
    /** Names this pager among the page's navigations ("above the table", "below"). */
    label: string;
    page: number;
    size: number;
    total: number;
    /** False when `total` is a cap: there is no last page to jump to. */
    totalExact: boolean;
    hasNext: boolean;
    /** The address of a page. `near`: this page is close enough to the one shown for its cursor to apply. */
    hrefFor: (page: number, near: boolean) => string;
    /** Called when a page link is followed (the list moves focus to the results). */
    onNavigate: () => void;
    onSizeChange?: (size: PageSize) => void;
}

const base = 'focus-visible:ring-brand-500 inline-flex h-9 min-w-9 items-center justify-center rounded px-2 text-sm focus:outline-hidden focus-visible:ring-2';
const idle = 'text-black-800 hover:bg-black-200';
const current = 'bg-black-900 font-semibold text-white';
const off = 'text-black-400 cursor-not-allowed';

/**
 * First, previous, the pages around this one, next and last, as real links:
 * they open in a new tab, work from the keyboard (Tab, Enter) and put the
 * page in the URL. Previous, next and the nearby pages carry the shown page's
 * cursor (the server seeks to it, so they cost the same at any depth); first
 * and last need none. A capped total has no last page.
 */
export default function ResponsePager({ label, page, size, total, totalExact, hasNext, hrefFor, onNavigate, onSizeChange }: Props) {
    const { t } = useTranslation();
    const pages = Math.max(1, Math.ceil(total / size));
    // the last page that surely exists: the exact one, or the capped total's, one further while another follows
    const known = totalExact ? pages : Math.max(pages, page + (hasNext ? 1 : 0));
    const nearby = nearbyPages(page, known);
    const lastKnownHere = totalExact && page < pages;

    const link = (target: number, near: boolean, content: React.ReactNode, aria: string, extra?: string) => (
        <Link key={`${aria}-${target}`} href={hrefFor(target, near)} scroll={false} prefetch={false} aria-label={aria} className={cn(base, idle, extra)} onClick={onNavigate}>
            {content}
        </Link>
    );
    const disabled = (content: React.ReactNode, aria: string, title?: string) => (
        <span key={aria} role="link" aria-disabled="true" aria-label={aria} title={title} className={cn(base, off)}>
            {content}
        </span>
    );

    return (
        <div className="flex flex-wrap items-center justify-between gap-3">
            <nav aria-label={label} className="flex flex-wrap items-center gap-1">
                {page > 1 ? link(1, false, '«', t(text.first)) : disabled('«', t(text.first))}
                {page > 1 ? link(page - 1, true, '‹', t(text.previous)) : disabled('‹', t(text.previous))}
                {nearby.map((target) =>
                    target === page ? (
                        <span key={target} aria-current="page" aria-label={t(text.pageN, { n: target })} className={cn(base, current)}>
                            {target}
                        </span>
                    ) : (
                        link(target, true, target, t(text.pageN, { n: target }), Math.abs(target - page) > 1 ? 'hidden sm:inline-flex' : undefined)
                    )
                )}
                {hasNext ? link(page + 1, true, '›', t(text.next)) : disabled('›', t(text.next))}
                {lastKnownHere ? link(pages, false, '»', t(text.last)) : disabled('»', totalExact ? t(text.last) : `${t(text.last)}. ${t(text.lastUnavailable)}`, totalExact ? undefined : t(text.lastUnavailable))}
            </nav>
            {onSizeChange && (
                <label className="text-black-700 flex items-center gap-2 text-sm">
                    {t(text.pageSize)}
                    <select
                        className="border-black-300 text-black-900 focus-visible:ring-brand-500 h-9 rounded border bg-white px-2 text-sm focus:outline-hidden focus-visible:ring-2"
                        value={size}
                        onChange={(event) => onSizeChange(Number(event.target.value) as PageSize)}
                    >
                        {PAGE_SIZES.map((option) => (
                            <option key={option} value={option}>
                                {option}
                            </option>
                        ))}
                    </select>
                </label>
            )}
        </div>
    );
}

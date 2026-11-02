'use client';

import { RefObject, useLayoutEffect, useRef, useState } from 'react';

import { Play } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import FormSlidePreview from '@app/views/organism/form-preview/form-slide-preview';
import WelcomePage from '@app/views/organism/form/welcome-page';
import LayoutWrapper from '@app/views/organism/layout/layout-wrapper';

/** The gap of the grid below (`gap-6`) and the width from which it has two columns (`lg`). */
const GRID_GAP = 24;
const TWO_COLUMNS_FROM = 1024;

/**
 * The width of one card: the grid's own width (which depends on the side menu and the page padding) shared by its
 * columns. It follows the grid when the window or the side menu changes size.
 */
function useCardWidth(grid: RefObject<HTMLElement | null>) {
    const [width, setWidth] = useState(0);
    useLayoutEffect(() => {
        const element = grid.current;
        if (!element) return;
        const measure = () => {
            const columns = window.innerWidth >= TWO_COLUMNS_FROM ? 2 : 1;
            setWidth(Math.max(0, Math.floor((element.clientWidth - GRID_GAP * (columns - 1)) / columns)));
        };
        measure();
        const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure);
        observer?.observe(element);
        window.addEventListener('resize', measure);
        return () => {
            observer?.disconnect();
            window.removeEventListener('resize', measure);
        };
    }, [grid]);
    return width;
}

export const FormTabContent = ({ form }: { form: StandardFormDto }) => {
    const { t } = useTranslation();
    const { openModal: openFullScreenModal } = useFullScreenModal();

    const grid = useRef<HTMLDivElement>(null);
    const containerWidth = useCardWidth(grid);

    const previewStyles = {
        scale: (containerWidth / 1440).toString(),
        transformOrigin: 'top left' as const
    };

    const openPreview = () => openFullScreenModal('PREVIEW_MODAL');

    const isSlideEmpty = (slide: StandardFormFieldDto) => !slide?.properties?.fields?.length;

    // A form imported from elsewhere has no pages of ours to show.
    if (form?.builderVersion !== 'v2') {
        return (
            <p data-testid="pages-not-available" className="text-black-700 max-w-[62ch] text-sm leading-relaxed">
                {t('STAFF.FORM_PAGES.NOT_AVAILABLE')}
            </p>
        );
    }

    return (
        <div className="flex w-full flex-col gap-4">
            <div className="flex items-center justify-between">
                <span className="text-black-600 text-xs font-semibold uppercase tracking-wide">{t('STAFF.FORM_PAGES.PAGES')}</span>
                <Button variant="v2Button" icon={<Play className="h-4 w-4" />} onClick={openPreview}>
                    {t('STAFF.FORM_PAGES.OPEN_PREVIEW')}
                </Button>
            </div>
            <div ref={grid} className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <PreviewCard label={t('STAFF.FORM_PAGES.WELCOME')} width={containerWidth} onClick={openPreview}>
                    <div className="pointer-events-none h-[810px] w-[1440px]" style={previewStyles}>
                        <LayoutWrapper showDesktopLayout theme={form?.theme} disabled layout={form.welcomePage?.layout} imageUrl={form?.welcomePage?.imageUrl}>
                            <WelcomePage isPreviewMode theme={form?.theme} welcomePageData={form?.welcomePage} />
                        </LayoutWrapper>
                    </div>
                </PreviewCard>
                {form?.fields?.map((slide, index) => (
                    <PreviewCard key={slide?.id} label={t('STAFF.FORM_PAGES.PAGE_N', { n: index + 1 })} empty={isSlideEmpty(slide)} width={containerWidth} onClick={openPreview}>
                        <div className="pointer-events-none h-[810px] w-[1440px]" style={previewStyles}>
                            <FormSlidePreview slide={slide} theme={form.theme} />
                        </div>
                    </PreviewCard>
                ))}
            </div>
        </div>
    );
};

/**
 * A labelled page thumbnail that actually does something on click: it opens
 * the full-screen preview (the scaled-down card itself is unreadable by
 * design — it is a map, not the territory).
 */
const PreviewCard = ({ label, empty, width, onClick, children }: { label: string; empty?: boolean; width: number; onClick: () => void; children: React.ReactNode }) => {
    const { t } = useTranslation();
    return (
    // div-with-button-role, NOT a <button>: the thumbnail renders the real
    // slide markup, which contains buttons/inputs of its own — interactive
    // elements can't nest inside a button.
    <div
        role="button"
        tabIndex={0}
        onClick={onClick}
        onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick();
            }
        }}
        className="group flex w-min cursor-pointer flex-col gap-1.5 text-left focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-[#123FC9]"
        aria-label={t('STAFF.FORM_PAGES.OPEN_AT', { label })}
    >
        <span className="text-black-700 flex items-center gap-2 text-[13px] font-medium">
            {label}
            {empty && <span className="bg-black-200 text-black-600 rounded-full px-2 py-0.5 text-xs">{t('STAFF.FORM_PAGES.EMPTY')}</span>}
        </span>
        <span className="border-black-300 group-hover:border-black-500 relative block aspect-video overflow-hidden rounded-md border transition-colors" style={{ width }}>
            {children}
        </span>
    </div>
    );
};

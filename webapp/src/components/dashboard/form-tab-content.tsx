'use client';

import { useEffect, useState } from 'react';

import { Play } from 'lucide-react';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import FormSlidePreview from '@app/views/organism/form-preview/form-slide-preview';
import WelcomePage from '@app/views/organism/form/welcome-page';
import LayoutWrapper from '@app/views/organism/layout/layout-wrapper';

const computeContainerWidth = () => {
    if (typeof window === 'undefined') return 0;
    const windowWidth = window.innerWidth;
    let padding = 5 * 4 * 2;
    if (windowWidth > 768) padding = 10 * 4 * 2;
    if (windowWidth > 1024) padding = 28 * 4 * 2 + 4 * 4;
    let containerWidth = windowWidth - padding;
    if (windowWidth > 1024) containerWidth = containerWidth / 2;
    return containerWidth;
};

export const FormTabContent = ({ form }: { form: StandardFormDto }) => {
    const { openModal: openFullScreenModal } = useFullScreenModal();

    // Track the width so the grid survives a window resize (it used to be
    // computed once at mount).
    const [containerWidth, setContainerWidth] = useState(computeContainerWidth);
    useEffect(() => {
        const onResize = () => setContainerWidth(computeContainerWidth());
        window.addEventListener('resize', onResize);
        return () => window.removeEventListener('resize', onResize);
    }, []);

    const previewStyles = {
        scale: (containerWidth / 1440).toString(),
        transformOrigin: 'top left' as const
    };

    const openPreview = () => openFullScreenModal('PREVIEW_MODAL');

    const isSlideEmpty = (slide: StandardFormFieldDto) => !slide?.properties?.fields?.length;

    if (form?.builderVersion !== 'v2') return null;

    return (
        <div className="flex w-full flex-col gap-4">
            <div className="flex items-center justify-between">
                <span className="text-black-600 text-xs font-semibold uppercase tracking-wide">Pages</span>
                <Button variant="v2Button" icon={<Play className="h-4 w-4" />} onClick={openPreview}>
                    Open preview
                </Button>
            </div>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <PreviewCard label="Welcome page" width={containerWidth} onClick={openPreview}>
                    <div className="pointer-events-none h-[810px] w-[1440px]" style={previewStyles}>
                        <LayoutWrapper showDesktopLayout theme={form?.theme} disabled layout={form.welcomePage?.layout} imageUrl={form?.welcomePage?.imageUrl}>
                            <WelcomePage isPreviewMode theme={form?.theme} welcomePageData={form?.welcomePage} />
                        </LayoutWrapper>
                    </div>
                </PreviewCard>
                {form?.fields?.map((slide, index) => (
                    <PreviewCard key={slide?.id} label={`Page ${index + 1}`} empty={isSlideEmpty(slide)} width={containerWidth} onClick={openPreview}>
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
const PreviewCard = ({ label, empty, width, onClick, children }: { label: string; empty?: boolean; width: number; onClick: () => void; children: React.ReactNode }) => (
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
        className="group flex w-min cursor-pointer flex-col gap-1.5 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#2456CC]"
        aria-label={`Open preview at ${label}`}
    >
        <span className="text-black-700 flex items-center gap-2 text-[13px] font-medium">
            {label}
            {empty && <span className="bg-black-200 text-black-600 rounded-full px-2 py-0.5 text-xs">Empty</span>}
        </span>
        <span className="border-black-300 group-hover:border-black-500 relative block aspect-video overflow-hidden rounded-md border transition-colors" style={{ width }}>
            {children}
        </span>
    </div>
);

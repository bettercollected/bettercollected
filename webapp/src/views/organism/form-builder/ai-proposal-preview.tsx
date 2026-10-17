'use client';

import { ChevronLeft, ChevronRight } from 'lucide-react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useAIProposalPreview } from '@app/store/jotai/ai-proposal';
import SlideBuilder from '@app/views/organism/form-builder/slide-builder';

function proposedPages(form: any): StandardFormFieldDto[] {
    return ((form?.fields ?? []) as StandardFormFieldDto[]).filter((field) => field?.type === 'slide');
}

/** The proposed page to show: the chosen one, else the open page, else the first. */
function usePreviewPage(activeSlideId?: string | null) {
    const { proposal, preview, setPreview } = useAIProposalPreview();
    const pages = proposedPages(proposal?.form);
    const wanted = preview.pageId ?? activeSlideId;
    const index = Math.max(
        0,
        pages.findIndex((page) => page.id === wanted)
    );
    return { on: preview.on && pages.length > 0, pages, index, page: pages[index], proposal, setPreview };
}

/**
 * The open AI proposal's version of a page, in the canvas, read-only: it is
 * rendered from the proposal's form and never from (or into) the editor
 * state, and ``inert`` keeps every editor inside it from taking input.
 */
export function AIProposalPreviewCanvas({ activeSlideId }: { activeSlideId?: string | null }) {
    const { on, page, proposal } = usePreviewPage(activeSlideId);
    if (!on || !page) return null;
    return (
        <div inert aria-label="Preview of the proposed changes, read-only" data-testid="ai-proposal-preview" className="h-full w-full">
            <SlideBuilder slide={page} disabled themeOverride={proposal?.form?.theme ?? undefined} />
        </div>
    );
}

/** Says the canvas shows a proposal, pages through it, and leaves it. */
export function AIProposalPreviewBar({ activeSlideId }: { activeSlideId?: string | null }) {
    const { on, pages, index, setPreview } = usePreviewPage(activeSlideId);
    if (!on) return null;
    const go = (to: number) => setPreview({ on: true, pageId: pages[to]?.id });
    return (
        <div role="status" className="flex items-center gap-2 rounded border border-[#E7C9A1] bg-[#FDF3E7] px-3 py-1.5 text-xs text-[#5C3A0A]">
            <span className="font-semibold">Previewing the AI&apos;s proposal</span>
            <span>Read-only · page {index + 1} of {pages.length}</span>
            <button type="button" aria-label="Previous proposed page" disabled={index === 0} onClick={() => go(index - 1)} className="rounded p-0.5 hover:bg-white/60 disabled:opacity-40">
                <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <button type="button" aria-label="Next proposed page" disabled={index >= pages.length - 1} onClick={() => go(index + 1)} className="rounded p-0.5 hover:bg-white/60 disabled:opacity-40">
                <ChevronRight className="h-3.5 w-3.5" />
            </button>
            <button type="button" onClick={() => setPreview({ on: false })} className="ml-1 rounded border border-[#E7C9A1] bg-white px-2 py-0.5 font-medium hover:bg-[#FFF8EF]">
                Exit preview
            </button>
        </div>
    );
}

export function useProposalPreviewOn(): boolean {
    const { proposal, preview } = useAIProposalPreview();
    return preview.on && proposedPages(proposal?.form).length > 0;
}

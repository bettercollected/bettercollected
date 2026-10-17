import { useMemo } from 'react';

import { atom, useAtom, useAtomValue } from 'jotai';

import { AIProposal, ProposalChangeGroup, ProposalHighlights, proposalHighlights } from '@app/utils/ai-proposal';

interface OpenProposal {
    proposal: AIProposal;
    groups: ProposalChangeGroup[];
}

interface ProposalPreview {
    on: boolean;
    /** The proposed page the canvas shows; the open page when it exists there. */
    pageId?: string | null;
}

/**
 * The AI proposal waiting for the person (one at a time), shared by the AI
 * tab, the canvas and the page rail. Nothing here touches the editor state:
 * previewing renders the proposed form read-only, and only accepting applies
 * the server's form to the canvas.
 */
const openProposalAtom = atom<OpenProposal | null>(null);
const proposalPreviewAtom = atom<ProposalPreview>({ on: false });

export function useOpenAIProposal() {
    const [openProposal, setOpenProposal] = useAtom(openProposalAtom);
    const [preview, setPreview] = useAtom(proposalPreviewAtom);
    const close = () => {
        setOpenProposal(null);
        setPreview({ on: false });
    };
    return { openProposal, setOpenProposal, preview, setPreview, close };
}

const EMPTY: ProposalHighlights = { fields: {}, pages: {} };

/** Fields and pages the open proposal adds or changes. */
export function useAIProposalHighlights(): ProposalHighlights {
    const openProposal = useAtomValue(openProposalAtom);
    return useMemo(() => (openProposal ? proposalHighlights(openProposal.groups) : EMPTY), [openProposal]);
}

export function useAIProposalPreview() {
    const openProposal = useAtomValue(openProposalAtom);
    const [preview, setPreview] = useAtom(proposalPreviewAtom);
    return { proposal: openProposal?.proposal ?? null, preview: openProposal ? preview : { on: false }, setPreview };
}

'use client';

import { Shield } from 'lucide-react';

export interface TrustLayerProps {
    /** Who is collecting the responses — the workspace/brand name. */
    ownerName?: string;
    /** Optional owner logo/avatar. */
    ownerImage?: string;
    /** Optional one-line statement of why the form collects data. */
    purpose?: string;
    /** Link to how the data is handled (form- or workspace-level privacy policy). */
    privacyUrl?: string;
    /** Human-readable retention, e.g. "kept for 90 days". */
    retention?: string;
    /** Link to the responder portal where a submission can be viewed/deleted. */
    portalUrl?: string;
}

/**
 * A quiet, persistent "trust layer" for the responder form: who is collecting,
 * why, how the data is handled, and the right to delete. Making the privacy
 * story visible on every form is bettercollected's differentiator — see
 * Design-Language.md §4.
 *
 * Presentational only: pass in data (see the wired usage on the fill page).
 */
export default function TrustLayer({ ownerName, ownerImage, purpose, privacyUrl, retention, portalUrl }: TrustLayerProps) {
    const items: React.ReactNode[] = [];

    if (ownerName) {
        items.push(
            <span key="owner" className="text-black-700 inline-flex items-center gap-1.5">
                {ownerImage ? (
                    <img src={ownerImage} alt="" className="h-4 w-4 rounded-full object-cover" />
                ) : null}
                Collected by <span className="text-black-900 font-semibold">{ownerName}</span>
            </span>
        );
    }
    if (purpose) {
        items.push(<span key="purpose" className="text-black-700">{purpose}</span>);
    }
    if (privacyUrl) {
        items.push(
            <a key="privacy" href={privacyUrl} target="_blank" rel="noopener noreferrer" className="text-brand-500 pointer-events-auto hover:underline">
                How your data is used
            </a>
        );
    }
    // Deletion is a right responders always have (post-submission); when we know
    // where to exercise it, say so with a link — otherwise state it plainly.
    items.push(
        portalUrl ? (
            <a key="delete" href={portalUrl} target="_blank" rel="noopener noreferrer" className="text-black-700 pointer-events-auto underline decoration-dotted underline-offset-2 hover:text-black-900">
                View or delete your response anytime{retention ? ` · ${retention}` : ''}
            </a>
        ) : (
            <span key="delete" className="text-black-700">
                You can view or delete your response anytime{retention ? ` · ${retention}` : ''}
            </span>
        )
    );

    return (
        // 13px legible ink-2 — the strip that carries the product's differentiator
        // shouldn't be the smallest text on screen (Design-Language §4).
        <div className="border-t-black-200 bg-white/85 flex w-full flex-wrap items-center justify-center gap-x-3 gap-y-1.5 border-t px-4 py-2.5 text-[13px] backdrop-blur-sm">
            <Shield className="text-brand-500 h-4 w-4 shrink-0" strokeWidth={1.8} aria-hidden="true" />
            {items.map((item, i) => (
                <span key={i} className="inline-flex items-center gap-3">
                    {i > 0 && <span className="bg-black-200 h-3 w-px" aria-hidden="true" />}
                    {item}
                </span>
            ))}
        </div>
    );
}

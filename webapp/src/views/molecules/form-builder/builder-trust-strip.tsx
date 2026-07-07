'use client';

import { Shield } from 'lucide-react';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useActiveFieldComponent } from '@app/store/jotai/active-builder-component';
import { usePropertiesTab } from '@app/store/jotai/properties-tab';
import { selectWorkspace } from '@app/store/workspaces/slice';
import TrustLayer from '@app/views/molecules/form/trust-layer';

/**
 * The responder-facing trust strip, rendered at the bottom of every builder
 * slide exactly as responders will see it. Creators shouldn't have to publish
 * (or even Preview) to know what privacy story their form tells — and seeing
 * the strip half-empty is the nudge to finish it.
 */
export function BuilderTrustStrip() {
    const workspace = useAppSelector(selectWorkspace);
    const standardForm = useAppSelector(selectForm);
    return (
        <TrustLayer
            ownerName={workspace?.title || workspace?.workspaceName}
            ownerImage={workspace?.profileImage}
            purpose={standardForm?.settings?.purpose}
            retention={standardForm?.settings?.retentionText}
            privacyUrl={standardForm?.settings?.privacyPolicyUrl}
            poweredBy={!standardForm?.settings?.disableBranding}
        />
    );
}

/**
 * Builder-chrome nudge shown while the trust content is empty: names what
 * responders see and deep-links to the Form tab where it's authored.
 * Disappears as soon as any of purpose / retention / privacy link is set.
 */
export function TrustStripNudge() {
    const standardForm = useAppSelector(selectForm);
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { setPropertiesTab } = usePropertiesTab();

    const settings = standardForm?.settings;
    if (settings?.purpose || settings?.retentionText || settings?.privacyPolicyUrl) return null;

    return (
        <button
            type="button"
            onClick={(event) => {
                event.stopPropagation();
                // The drawer shows tabs only while no field is selected.
                setActiveFieldComponent(null);
                setPropertiesTab('form');
            }}
            className="border-black-300 hover:border-[#2456CC] flex max-w-[90%] items-center gap-2 rounded-full border bg-white px-4 py-2 text-xs shadow-sm transition-colors"
        >
            <Shield className="h-3.5 w-3.5 shrink-0 text-[#2456CC]" strokeWidth={1.8} aria-hidden="true" />
            <span className="text-black-700 truncate">Responders see this footer on every page — say why you&apos;re collecting and how long you keep answers.</span>
            <span className="shrink-0 font-semibold text-[#2456CC]">Add it →</span>
        </button>
    );
}

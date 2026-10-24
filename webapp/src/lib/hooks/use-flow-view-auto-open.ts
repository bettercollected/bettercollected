'use client';

import { useEffect, useRef } from 'react';

import { useStore } from 'jotai';

import { builderHydratedFormIdAtom } from '@app/store/jotai/builder-hydration';
import { builderFieldsAtom } from '@app/store/jotai/form-document';
import { hasBuildReport } from '@app/utils/ai-build-report';
import { slideHasLogic } from '@app/utils/conditional-logic';

/** Where the creator's choice of view for a form is remembered. */
export const defaultViewKey = (formId: string) => `bc-default-view-${formId}`;

function choseView(formId: string): boolean {
    try {
        return !!localStorage.getItem(defaultViewKey(formId));
    } catch {
        return false;
    }
}

/**
 * Default-view heuristic: a form that already branches when it is opened
 * opens in the Flow view. Decided once per form, on the form as loaded (the
 * editor marks it loaded once its pages are in the builder): adding the
 * first logic while editing does not switch views under the creator. A
 * creator who closed the Flow view for this form keeps the page view, and a
 * form just built from an AI outline opens on its checklist first.
 */
export function useFlowViewAutoOpen(formId: string | undefined, open: () => void) {
    const store = useStore();
    const decidedFor = useRef<string | null>(null);
    const openRef = useRef(open);
    useEffect(() => {
        openRef.current = open;
    });
    useEffect(() => {
        const check = () => {
            if (!formId || decidedFor.current === formId) return;
            if (store.get(builderHydratedFormIdAtom) !== formId) return;
            decidedFor.current = formId;
            const formFields = store.get(builderFieldsAtom);
            // Defensive: the atom can transiently hold non-array state.
            if (!Array.isArray(formFields) || !formFields.some((slide) => slideHasLogic(slide))) return;
            if (choseView(formId) || hasBuildReport(formId)) return;
            openRef.current();
        };
        check();
        return store.sub(builderHydratedFormIdAtom, check);
    }, [formId, store]);
}

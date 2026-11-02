'use client';

import { useEffect, useRef } from 'react';

import { heightChanged, measureNeededHeight, scrollAreaOf } from '@app/lib/embed/embed-height';
import { guardLinks } from '@app/lib/embed/embed-links';
import { heightMessage, loadedMessage, postToParent, submittedMessage } from '@app/lib/embed/embed-messages';
import { useEmbed } from '@app/lib/embed/use-embed';
import { useAppSelector } from '@app/store/hooks';
import { useResponderState, useShownSlide } from '@app/store/jotai/responder-form-state';
import { useGetEmbedPolicyQuery } from '@app/store/workspaces/embed-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

/** Moments, after a page change, at which the new page is measured again (the page slides in over 350 ms). */
const REMEASURE_AFTER_MS = [0, 120, 450];
/** The page's height must stay the same this long before it is reported. */
const SETTLE_MS = 80;

/**
 * In embed mode (a frame on another site, docs/embed.md) tells the page around the form that it loaded, how
 * tall it needs to be and that it was submitted. Only those three: the messages are built from fixed fields
 * (lib/embed/embed-messages.ts), with no page number or counter (the number of pages a respondent sees can
 * depend on their answers when a form branches). The height is the one thing that still varies with the page
 * on screen.
 *
 * It tells the page around it only while this server has embedding switched on (the public embed policy
 * says so): with the switch off a site that frames a form anyway learns nothing. Renders nothing, and
 * outside embed mode does nothing. In embed mode it also sends links that leave the form's page to a new tab.
 */
export default function EmbedReporter() {
    const { embedded, parentOrigin } = useEmbed();
    const { responderState } = useResponderState();
    const slide = useShownSlide();
    const workspace = useAppSelector(selectWorkspace);
    const policy = useGetEmbedPolicyQuery(workspace?.id as string, { skip: !embedded || !parentOrigin || !workspace?.id });
    // messages only while the server's switch is on
    const active = embedded && policy.data?.enabled === true;
    const submitted = slide === -2 && !!responderState.responderId;
    const lastHeight = useRef<number | null>(null);
    const sentSubmitted = useRef(false);
    const sentLoaded = useRef(false);

    useEffect(() => {
        if (!embedded) return;
        document.documentElement.setAttribute('data-bc-embed', '');
        const stop = guardLinks();
        return () => {
            stop();
            document.documentElement.removeAttribute('data-bc-embed');
        };
    }, [embedded]);

    useEffect(() => {
        if (!active || sentLoaded.current) return;
        sentLoaded.current = true;
        postToParent(loadedMessage(), parentOrigin);
    }, [active, parentOrigin]);

    useEffect(() => {
        if (!active || !submitted || sentSubmitted.current) return;
        sentSubmitted.current = true;
        postToParent(submittedMessage(), parentOrigin);
    }, [active, parentOrigin, submitted]);

    useEffect(() => {
        if (!active) return;
        let pending: number | undefined;
        const report = () => {
            pending = undefined;
            const needed = measureNeededHeight(document, window.innerHeight, slide);
            if (needed === null || !heightChanged(lastHeight.current, needed)) return;
            lastHeight.current = needed;
            postToParent(heightMessage(needed), parentOrigin);
        };
        // Reported once the page has settled for a moment: a layout that is still finding its size
        // (fonts, images, a slide moving in) must not make the frame jump on the page around it.
        const schedule = () => {
            if (pending !== undefined) window.clearTimeout(pending);
            pending = window.setTimeout(report, SETTLE_MS);
        };
        const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(schedule);
        // The page's content and the strip below it change size by themselves (an error message, the
        // privacy panel opening); the frame's own size follows from what is reported.
        const observe = () => {
            const content = scrollAreaOf(document, slide)?.firstElementChild;
            if (content) observer?.observe(content);
            const footer = document.querySelector('footer');
            if (footer) observer?.observe(footer);
            schedule();
        };
        const timers = REMEASURE_AFTER_MS.map((ms) => window.setTimeout(observe, ms));
        window.addEventListener('resize', schedule);
        return () => {
            timers.forEach((timer) => window.clearTimeout(timer));
            window.removeEventListener('resize', schedule);
            observer?.disconnect();
            if (pending !== undefined) window.clearTimeout(pending);
        };
    }, [active, parentOrigin, slide]);

    return null;
}

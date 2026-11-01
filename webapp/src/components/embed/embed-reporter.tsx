'use client';

import { useEffect, useRef } from 'react';

import { heightChanged, measureNeededHeight, scrollAreaOf } from '@app/lib/embed/embed-height';
import { guardLinks } from '@app/lib/embed/embed-links';
import { PageKind, heightMessage, loadedMessage, pageMessage, postToParent, submittedMessage } from '@app/lib/embed/embed-messages';
import { useEmbed } from '@app/lib/embed/use-embed';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useResponderState, useShownSlide } from '@app/store/jotai/responder-form-state';
import { REVIEW_SLIDE } from '@app/utils/review-page';

/** welcome (-1), review, ending (-2), else a question page. */
export function pageKindOf(slide: number): PageKind {
    if (slide === -1) return 'welcome';
    if (slide === REVIEW_SLIDE) return 'review';
    if (slide === -2) return 'ending';
    return 'question';
}

/** Moments, after a page change, at which the new page is measured again (the page slides in over 350 ms). */
const REMEASURE_AFTER_MS = [0, 120, 450];
/** The page's height must stay the same this long before it is reported. */
const SETTLE_MS = 80;

/**
 * In embed mode (a frame on another site, docs/embed.md) tells the page around the form that it loaded,
 * which kind of page it is on, how tall it needs to be and that it was submitted. Only those: the
 * messages are built from fixed fields (lib/embed/embed-messages.ts). Renders nothing, and does nothing
 * outside embed mode. It also sends links that leave the form's page to a new tab.
 */
export default function EmbedReporter() {
    const { embedded, parentOrigin } = useEmbed();
    const { responderState } = useResponderState();
    const slide = useShownSlide();
    const form = useAppSelector(selectResponderForm);
    const total = form?.fields?.length ?? 0;
    const passed = responderState.history?.length ?? 0;
    const submitted = slide === -2 && !!responderState.responderId;
    const lastHeight = useRef<number | null>(null);
    const sentSubmitted = useRef(false);
    const sentLoaded = useRef(false);
    const lastPage = useRef('');

    useEffect(() => {
        if (!embedded) return;
        document.documentElement.setAttribute('data-bc-embed', '');
        const stop = guardLinks();
        if (!sentLoaded.current) {
            sentLoaded.current = true;
            postToParent(loadedMessage(), parentOrigin);
        }
        return () => {
            stop();
            document.documentElement.removeAttribute('data-bc-embed');
        };
    }, [embedded, parentOrigin]);

    useEffect(() => {
        if (!embedded) return;
        // the form's page count arrives a moment after the first page: say it again once it is known
        const key = `${pageKindOf(slide)}:${passed}:${total}`;
        if (key === lastPage.current) return;
        lastPage.current = key;
        postToParent(pageMessage(pageKindOf(slide), passed, total), parentOrigin);
    }, [embedded, parentOrigin, slide, passed, total]);

    useEffect(() => {
        if (!embedded || !submitted || sentSubmitted.current) return;
        sentSubmitted.current = true;
        postToParent(submittedMessage(), parentOrigin);
    }, [embedded, parentOrigin, submitted]);

    useEffect(() => {
        if (!embedded) return;
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
    }, [embedded, parentOrigin, slide]);

    return null;
}

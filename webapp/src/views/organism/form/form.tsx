import { useEffect, useRef } from 'react';

import { usePathname } from 'next/navigation';

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

import { useResponderFormLogo } from '@app/lib/hooks/use-form-logo';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { Progress } from '@app/shadcn/components/ui/progress';
import { cn } from '@app/shadcn/util/lib';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { endingToShow } from '@app/utils/endings';
import { progressPercent } from '@app/utils/form-progress';
import { respondentSignInUrl } from '@app/utils/respondent-lang-query';
import { greetingCover, hasPictureSlot } from '@app/views/molecules/theme/theme-artwork';
import { useBodyFormFace } from '@app/views/molecules/theme/theme-root';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';
import UserAvatarDropDown from '@app/views/molecules/user-avatar-dropdown';

import LayoutWrapper from '../layout/layout-wrapper';
import FormSlide from './form-slide';
import ThankyouPage from './thankyou-page';
import WelcomePage from './welcome-page';

/**
 * One slide transition for every page type. Each page used to declare its own
 * animation (different easings, no exit motion at all — the old page froze
 * while the new one covered it), and the ±100% fly-in wasn't clipped, so a
 * horizontal scrollbar flashed on every transition.
 *
 * The entering page slides the full width in the direction of travel; the
 * exiting page drifts a quarter width the other way while fading (parallax),
 * which reads as one continuous surface. Honors prefers-reduced-motion with a
 * plain cross-fade.
 */
const slideVariants = {
    enter: (direction: number) => ({ x: direction >= 0 ? '100%' : '-100%', opacity: 1 }),
    center: { x: 0, opacity: 1 },
    exit: (direction: number) => ({ x: direction >= 0 ? '-24%' : '24%', opacity: 0 })
};

const fadeVariants = {
    enter: { x: 0, opacity: 0 },
    center: { x: 0, opacity: 1 },
    exit: { x: 0, opacity: 0 }
};

/**
 * Where focus goes when the respondent moves to another page: the element
 * marked `data-page-start` in the new page ("Page x of y" on a question page,
 * the title on the welcome and ending pages). Without it, focus stayed on the
 * Continue button of the page that slid away and fell to the document when it
 * unmounted, so a keyboard user started again from the top of the document
 * and a screen reader announced nothing (WCAG 2.4.3). Focus already inside the
 * new page (a question focused for its error) is left where it is.
 */
export function focusPageStart(page: HTMLElement | null) {
    if (!page) return;
    const active = document.activeElement;
    if (active && active !== document.body && page.contains(active)) return;
    const start = page.querySelector<HTMLElement>('[data-page-start]') ?? page.querySelector<HTMLElement>('h1');
    if (!start) return;
    // A heading is a place to start reading, not a control: no focus ring.
    if (!start.hasAttribute('tabindex')) {
        start.setAttribute('tabindex', '-1');
        start.classList.add('outline-none');
    }
    start.focus({ preventScroll: true });
}

const slideTransition = { duration: 0.35, ease: [0.32, 0.72, 0, 1] as [number, number, number, number] };

const Form = ({ isPreviewMode = false, showDesktopLayout }: { isPreviewMode?: boolean; showDesktopLayout?: boolean }) => {
    const { currentSlide, prevActiveSlide: previousSlide, endingId } = useResponderState();
    const prefersReducedMotion = useReducedMotion();
    // The form is in the respondent's language; on the public pages <html lang>
    // says so too, and this also marks it inside the builder's preview.
    const { language } = useRespondentLanguage();

    const standardForm = useAppSelector(selectResponderForm);
    // Leaflet pages start with a full-width bar at the top edge.
    const topAligned = styleTokens(standardForm?.theme?.style).key === 'leaflet';
    // Popovers and toasts on the respondent page wear the theme's body face too.
    useBodyFormFace(standardForm?.theme?.bodyFont, !isPreviewMode);
    // The organisation logo strip on every page (DESIGN.md §9), larger on the cover.
    const logo = useResponderFormLogo();
    // With a logo strip, the account control moves into its row on the welcome
    // and ending pages, and the pages drop the row that held it.
    const workspace = useAppSelector(selectWorkspace);
    const pathname = usePathname();
    const responderSignInUrl = isPreviewMode ? '' : respondentSignInUrl(workspace?.id, pathname, language);
    // A welcome page set beside the theme's artwork is its cover (theme-artwork.tsx).
    const cover = greetingCover(standardForm.theme, standardForm.welcomePage?.layout, standardForm.welcomePage?.imageUrl, { privateForm: !!standardForm?.settings?.private });
    const ending = endingToShow(standardForm?.thankyouPage, endingId);

    // The bar says what "Page x of y" in the header says (utils/form-progress.ts).
    const { formResponse } = useFormResponse();
    const getProgressValue = () => progressPercent(standardForm?.fields, currentSlide, formResponse.answers || {});

    // Position of a slide along the journey: welcome → pages → thank-you.
    // The sentinels (-1 welcome, -2 thank-you) don't compare numerically.
    const ordinalOf = (slide: number) => {
        if (slide === -1) return 0;
        if (slide === -2) return (standardForm?.fields?.length || 0) + 1;
        return slide + 1;
    };
    const direction = ordinalOf(currentSlide) >= ordinalOf(previousSlide) ? 1 : -1;
    const variants = prefersReducedMotion ? fadeVariants : slideVariants;

    // Focus follows the respondent to each new page (focusPageStart), in
    // previews too; not on the first page shown. The new page is found by its
    // slide, not by a ref: while the old page slides out both are mounted.
    const formRef = useRef<HTMLDivElement>(null);
    const shownSlide = useRef(currentSlide);
    useEffect(() => {
        if (shownSlide.current === currentSlide) return;
        shownSlide.current = currentSlide;
        const frame = requestAnimationFrame(() => focusPageStart(formRef.current?.querySelector<HTMLElement>(`[data-slide="${currentSlide}"]`) ?? null));
        return () => cancelAnimationFrame(frame);
    }, [currentSlide]);

    return (
        // overflow-hidden clips the ±100% fly-in/out — without it the document
        // grows sideways mid-transition and a horizontal scrollbar flashes.
        <div ref={formRef} className={cn(isPreviewMode ? 'h-full w-full' : 'h-screen w-screen', 'relative h-full w-full overflow-hidden')} lang={language}>
            {currentSlide !== -1 && (
                // Decorative: "Page x of y" in the header says the same in words.
                <div className="absolute top-0 right-0 left-0 z-80!" aria-hidden="true">
                    <Progress indicatorColor={standardForm.theme?.secondary} value={getProgressValue()} className="h-1 rounded-none" style={{ background: standardForm.theme?.tertiary ? `${standardForm.theme.tertiary}33` : undefined }} />
                </div>
            )}
            <AnimatePresence mode="sync" initial={false} custom={direction}>
                <motion.div
                    key={currentSlide}
                    {...({
                        custom: direction,
                        variants,
                        initial: 'enter',
                        animate: 'center',
                        exit: 'exit',
                        transition: slideTransition,
                        className: 'absolute inset-0 z-10 flex h-full w-full flex-1 flex-col items-center justify-center'
                    } as any)}
                >
                    <div data-slide={currentSlide} className="relative h-full w-full">
                        {currentSlide === -1 && (
                            <LayoutWrapper
                                showDesktopLayout={showDesktopLayout}
                                theme={cover?.theme ?? standardForm.theme}
                                artworkTheme={standardForm.theme}
                                style={cover?.style}
                                disabled
                                layout={standardForm.welcomePage?.layout}
                                imageUrl={standardForm?.welcomePage?.imageUrl}
                                topAligned={topAligned}
                                logo={logo}
                                logoSize="cover"
                                logoAction={logo ? <UserAvatarDropDown inline responderSignInUrl={responderSignInUrl} /> : undefined}
                            >
                                <WelcomePage isPreviewMode={isPreviewMode} accountInStrip={!!logo} theme={cover?.theme} />
                            </LayoutWrapper>
                        )}
                        {currentSlide >= 0 && <FormSlide showDesktopLayout={showDesktopLayout} index={currentSlide} isPreviewMode={isPreviewMode} logo={logo} />}
                        {currentSlide === -2 && (
                            <LayoutWrapper
                                showDesktopLayout={showDesktopLayout}
                                theme={standardForm.theme}
                                disabled
                                layout={ending?.layout}
                                imageUrl={ending?.imageUrl}
                                topAligned={topAligned}
                                // The theme's artwork runs along the top of an ending without a picture half.
                                artworkBand={!hasPictureSlot(ending?.layout)}
                                logo={logo}
                                logoAction={logo ? <UserAvatarDropDown inline disabled /> : undefined}
                            >
                                <ThankyouPage isPreviewMode={isPreviewMode} accountInStrip={!!logo} />
                            </LayoutWrapper>
                        )}
                    </div>
                </motion.div>
            </AnimatePresence>
        </div>
    );
};

export default Form;

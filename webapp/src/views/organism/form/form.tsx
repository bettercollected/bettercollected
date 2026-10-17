import { usePathname } from 'next/navigation';

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

import { useResponderFormLogo } from '@app/lib/hooks/use-form-logo';
import { Progress } from '@app/shadcn/components/ui/progress';
import { cn } from '@app/shadcn/util/lib';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { endingToShow } from '@app/utils/endings';
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

const slideTransition = { duration: 0.35, ease: [0.32, 0.72, 0, 1] as [number, number, number, number] };

const Form = ({ isPreviewMode = false, showDesktopLayout }: { isPreviewMode?: boolean; showDesktopLayout?: boolean }) => {
    const { currentSlide, prevActiveSlide: previousSlide, endingId } = useResponderState();
    const prefersReducedMotion = useReducedMotion();

    const standardForm = useAppSelector(selectResponderForm);
    // Leaflet pages start with a full-width bar at the top edge.
    const topAligned = styleTokens(standardForm?.theme?.style).key === 'leaflet';
    // The organisation logo strip on every page (DESIGN.md §9), larger on the cover.
    const logo = useResponderFormLogo();
    // With a logo strip, the account control moves into its row on the welcome
    // and ending pages, and the pages drop the row that held it.
    const workspace = useAppSelector(selectWorkspace);
    const pathname = usePathname();
    const responderSignInUrl = isPreviewMode ? '' : `/login?type=responder&workspace_id=${workspace?.id}&redirect_to=${pathname}`;

    const getProgressValue = () => {
        const totalSlides = (standardForm?.fields?.length || 0) + 2;
        let currentSlideIndex = 1;
        if (currentSlide >= 0) {
            currentSlideIndex = currentSlide + 2;
        }
        if (currentSlide === -2) currentSlideIndex = (standardForm.fields?.length || 0) + 2;
        return (currentSlideIndex / totalSlides) * 100;
    };

    // Position of a slide along the journey: welcome → pages → thank-you.
    // The sentinels (-1 welcome, -2 thank-you) don't compare numerically.
    const ordinalOf = (slide: number) => {
        if (slide === -1) return 0;
        if (slide === -2) return (standardForm?.fields?.length || 0) + 1;
        return slide + 1;
    };
    const direction = ordinalOf(currentSlide) >= ordinalOf(previousSlide) ? 1 : -1;
    const variants = prefersReducedMotion ? fadeVariants : slideVariants;

    return (
        // overflow-hidden clips the ±100% fly-in/out — without it the document
        // grows sideways mid-transition and a horizontal scrollbar flashes.
        <div className={cn(isPreviewMode ? 'h-full w-full' : 'h-screen w-screen', 'relative h-full w-full overflow-hidden')}>
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
                    <div className="relative h-full w-full">
                        {currentSlide === -1 && (
                            <LayoutWrapper
                                showDesktopLayout={showDesktopLayout}
                                theme={standardForm.theme}
                                disabled
                                layout={standardForm.welcomePage?.layout}
                                imageUrl={standardForm?.welcomePage?.imageUrl}
                                topAligned={topAligned}
                                logo={logo}
                                logoSize="cover"
                                logoAction={logo ? <UserAvatarDropDown inline responderSignInUrl={responderSignInUrl} /> : undefined}
                            >
                                <WelcomePage isPreviewMode={isPreviewMode} accountInStrip={!!logo} />
                            </LayoutWrapper>
                        )}
                        {currentSlide >= 0 && <FormSlide showDesktopLayout={showDesktopLayout} index={currentSlide} isPreviewMode={isPreviewMode} logo={logo} />}
                        {currentSlide === -2 && (
                            <LayoutWrapper
                                showDesktopLayout={showDesktopLayout}
                                theme={standardForm.theme}
                                disabled
                                layout={endingToShow(standardForm?.thankyouPage, endingId)?.layout}
                                imageUrl={endingToShow(standardForm?.thankyouPage, endingId)?.imageUrl}
                                topAligned={topAligned}
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

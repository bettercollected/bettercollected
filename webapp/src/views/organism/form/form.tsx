import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

import { Progress } from '@app/shadcn/components/ui/progress';
import { cn } from '@app/shadcn/util/lib';
import { useResponderState } from '@app/store/jotai/responder-form-state';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
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
    const { currentSlide, prevActiveSlide: previousSlide } = useResponderState();
    const prefersReducedMotion = useReducedMotion();

    const standardForm = useAppSelector(selectForm);

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
        <div className={cn(isPreviewMode ? 'h-full w-full  ' : 'h-screen w-screen', 'relative h-full w-full overflow-hidden')}>
            {currentSlide !== -1 && (
                <div className="absolute left-0 right-0 top-0 !z-[80]">
                    <Progress indicatorColor={standardForm.theme?.secondary} value={getProgressValue()} className="h-1 rounded-none" />
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
                            <LayoutWrapper removePaddingXForSmallScreen showDesktopLayout={showDesktopLayout} theme={standardForm.theme} disabled layout={standardForm.welcomePage?.layout} imageUrl={standardForm?.welcomePage?.imageUrl}>
                                <WelcomePage isPreviewMode={isPreviewMode} />
                            </LayoutWrapper>
                        )}
                        {currentSlide >= 0 && <FormSlide showDesktopLayout={showDesktopLayout} index={currentSlide} isPreviewMode={isPreviewMode} />}
                        {currentSlide === -2 && (
                            <LayoutWrapper showDesktopLayout={showDesktopLayout} theme={standardForm.theme} disabled layout={standardForm?.thankyouPage?.[0]?.layout} imageUrl={standardForm?.thankyouPage?.[0]?.imageUrl}>
                                <ThankyouPage isPreviewMode={isPreviewMode} />
                            </LayoutWrapper>
                        )}
                    </div>
                </motion.div>
            </AnimatePresence>
        </div>
    );
};

export default Form;

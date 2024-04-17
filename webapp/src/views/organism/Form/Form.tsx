import { AnimatePresence, motion } from 'framer-motion';

import { Progress } from '@app/shadcn/components/ui/progress';
import { cn } from '@app/shadcn/util/lib';
import { useResponderState } from '@app/store/jotai/responderFormState';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import LayoutWrapper from '../Layout/LayoutWrapper';
import FormSlide from './FormSlide';
import ThankyouPage from './ThankyouPage';
import WelcomePage from './WelcomePage';

const Form = ({ isPreviewMode = false, isMobileView = false }: { isPreviewMode?: boolean; isMobileView?: boolean }) => {
    const { currentSlide, prevActiveSlide: previousSlide } = useResponderState();

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

    return (
        <div className={cn(isPreviewMode || isMobileView ? 'h-full w-full  ' : 'h-screen w-screen', 'relative h-full w-full')}>
            <div className="absolute left-0 right-0 top-0 !z-[80] bg-green-500">
                <Progress value={getProgressValue()} className="h-2 rounded-none" />
            </div>
            <AnimatePresence>
                {currentSlide === -1 && (
                    <motion.div
                        className={cn('absolute flex h-full w-full flex-1 flex-col items-center justify-center', isMobileView ? 'aspect-[9/20]' : '')}
                        key={'welcome-page'}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 1 }}
                        transition={{ duration: 0.5 }}
                    >
                        <div className="relative h-full w-full">
                            <LayoutWrapper theme={standardForm.theme} disabled layout={standardForm.welcomePage?.layout} imageUrl={standardForm?.welcomePage?.imageUrl}>
                                <WelcomePage isPreviewMode={isPreviewMode} />
                            </LayoutWrapper>
                        </div>
                    </motion.div>
                )}

                {currentSlide >= 0 && (
                    <motion.div
                        className={cn('absolute z-10 flex h-full w-full flex-1 flex-col items-center justify-center', isMobileView ? 'aspect-[9/20]' : '')}
                        key={currentSlide}
                        initial={{ opacity: 1, x: currentSlide > previousSlide ? '100%' : '-100%' }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.5, ease: 'linear' }}
                    >
                        <div className="relative h-full w-full">
                            <FormSlide index={currentSlide} isPreviewMode={isPreviewMode} />
                        </div>
                    </motion.div>
                )}
                {currentSlide === -2 && (
                    <motion.div
                        className={cn('absolute z-20 flex h-full w-full flex-1 flex-col items-center justify-center', isMobileView ? 'aspect-[9/20]' : '')}
                        key={'thank-you-page'}
                        initial={{ opacity: 1, x: '100%' }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.5, ease: 'linear' }}
                    >
                        <div className="relative h-full w-full">
                            <LayoutWrapper theme={standardForm.theme} disabled layout={standardForm?.thankyouPage?.[0]?.layout} imageUrl={standardForm?.thankyouPage?.[0]?.imageUrl}>
                                <ThankyouPage isPreviewMode={isPreviewMode} />
                            </LayoutWrapper>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default Form;

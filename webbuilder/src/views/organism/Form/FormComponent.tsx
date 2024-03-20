import { AnimatePresence, motion } from 'framer-motion';

import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';

import FormSlide from './FormSlide';
import ThankyouPage from './ThankyouPage';
import WelcomePage from './WelcomePage';

const FormComponent = () => {
    const { currentSlide } = useResponderState();

    return (
        <div className="h-screen w-screen">
            <AnimatePresence custom={currentSlide} mode="wait">
                {currentSlide === -1 && (
                    <motion.div
                        className="h-full"
                        key={'welcome-page'}
                        initial={{ opacity: 0, x: -100 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                    >
                        <WelcomePage />
                    </motion.div>
                )}

                {currentSlide >= 0 && (
                    <motion.div
                        className="h-full"
                        key={currentSlide}
                        initial={{ opacity: 0, x: -100 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                    >
                        <FormSlide index={currentSlide} />
                    </motion.div>
                )}

                {currentSlide === -2 && (
                    <motion.div
                        className="h-full"
                        key={'thank-you-page'}
                        initial={{ opacity: 0, x: -100 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                    >
                        <ThankyouPage />
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default FormComponent;

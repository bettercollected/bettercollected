import { AnimatePresence, motion } from 'framer-motion';

import { FormResponse } from '@app/store/jotai/responderFormResponse';

import FormSlide from './FormSlide';
import ThankyouPage from './ThankyouPage';
import WelcomePage from './WelcomePage';

const FormComponent = ({ formResponse }: { formResponse: FormResponse }) => {
    const currentSlide = formResponse.currentSlide;
    return (
        <div className="h-screen w-screen">
            <AnimatePresence custom={currentSlide} mode="wait">
                {formResponse.currentSlide === -1 && (
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

                {formResponse.currentSlide >= 0 && (
                    <motion.div
                        className="h-full"
                        key={formResponse.currentSlide}
                        initial={{ opacity: 0, x: -100 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                    >
                        <FormSlide index={formResponse.currentSlide} />
                    </motion.div>
                )}

                {formResponse.currentSlide === -2 && (
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

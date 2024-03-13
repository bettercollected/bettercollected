import { FormResponse } from '@app/store/jotai/responderFormResponse';

import FormSlide from './FormSlide';
import WelcomePage from './WelcomePage';
import ThankyouPage from './ThankyouPage';

const FormComponent = ({ formResponse }: { formResponse: FormResponse }) => {
    return (
        <div className="h-screen w-screen">
            {formResponse?.currentSlide === -1 && <WelcomePage />}
            {formResponse?.currentSlide === -2 && <ThankyouPage />}
            {formResponse?.currentSlide >= 0 && (
                <FormSlide index={formResponse.currentSlide} />
            )}
        </div>
    );
};

export default FormComponent;

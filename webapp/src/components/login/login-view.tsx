import React, { useRef } from 'react';

import { useTranslation } from 'next-i18next';

import LoginLayout from '@Components/Login/login-layout';

import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { formResponderLogin } from '@app/constants/locales/form-responder-login';

export default function LoginView(props: any) {
    const { closeModal } = useFullScreenModal();
    const { t } = useTranslation();

    const ref = useRef<HTMLDivElement>(null);

    const features = {
        heading: t(formResponderLogin.featureHeading),
        paragraphs: [t(formResponderLogin.feature1), t(formResponderLogin.feature2), t(formResponderLogin.feature3)]
    };

    return (
        <div ref={ref} className="relative z-50 mx-auto max-w-full w-full" {...props}>
            <LoginLayout isCreator={false} features={features} />
            <Close onClick={() => closeModal()} className="cursor-pointer absolute top-5 right-5 hover:text-black dark:text-white" />
        </div>
    );
}

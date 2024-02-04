import React, { useRef } from 'react';

import { useTranslation } from 'next-i18next';

import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { formResponderLogin } from '@app/constants/locales/form-responder-login';

import { SignInModal } from '../modal-views/modals/sign-in-modal';


export default function LoginView(props: any) {
    const { closeModal } = useFullScreenModal();
    const { t } = useTranslation();
    const closable = !props?.nonClosable;

    const ref = useRef<HTMLDivElement>(null);

    const features = {
        heading: t(formResponderLogin.featureHeading),
        paragraphs: [t(formResponderLogin.feature1), t(formResponderLogin.feature2), t(formResponderLogin.feature3)]
    };

    return (
        <div ref={ref} className="relative z-50 mx-auto my-auto w-screen overflow-auto xl:w-[1094px] min-h-screen xl:min-h-[687px] xl:h-[687px] bg-brand-100 dark:bg-dark xl:rounded-lg" {...props}>
            <SignInModal isCreator={false} features={features} />
            {closable && <Close onClick={() => closeModal()} className="cursor-pointer fixed xl:absolute top-5 right-5 hover:text-black dark:text-white" />}
        </div>
    );
}
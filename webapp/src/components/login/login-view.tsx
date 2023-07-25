import React, { useRef } from 'react';

import { useTranslation } from 'next-i18next';

import LoginLayout from '@Components/Login/login-layout';

import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';

export default function LoginView(props: any) {
    const { closeModal } = useFullScreenModal();

    const ref = useRef<HTMLDivElement>(null);

    // return (
    //     <div ref={ref}
    //          className="relative z-50 mx-auto max-w-full w-full" {...props}>
    //         <div className="rounded-[4px] relative m-auto items-start justify-between bg-white">
    //             {isSuccess ? <OtpRenderer email={email} isCustomDomain={isCustomDomain}/> :
    //                 <SendCode updateEmail={updateEmail} isCustomDomain={isCustomDomain} isLoading={isLoading}
    //                           postSendOtp={postSendOtp}/>}
    //         </div>
    //         <Close onClick={() => closeModal()}
    //                className="cursor-pointer absolute top-5 right-5 hover:text-black dark:text-white"/>
    //     </div>
    // );

    const features = {
        heading: 'Once you sign in you will be able to:',
        paragraphs: ['See all forms of workspace', 'See all your submitted forms of that particular workspace.', 'Delete your submitted form responses']
    };

    const { t } = useTranslation();

    return (
        <div ref={ref} className="relative z-50 mx-auto max-w-full w-full" {...props}>
            <LoginLayout isCreator={false} features={features} />
            <Close onClick={() => closeModal()} className="cursor-pointer absolute top-5 right-5 hover:text-black dark:text-white" />
        </div>
    );
}

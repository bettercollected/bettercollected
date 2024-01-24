import React from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import HeaderModalWrapper from '@Components/Modals/ModalWrappers/HeaderModalWrapper';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';


export default function SignInToFillFormModal() {
    const { closeModal } = useModal();
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const onClickSignInButton = (event: React.MouseEvent<HTMLButtonElement>) => {
        closeModal();
        openFullScreenModal('LOGIN_VIEW', { nonClosable: true });
    };

    return (
        <HeaderModalWrapper showClose={false} headerTitle="Sign In">
            <span className="text-black-800 text-base font-semibold">Get Form Access</span>
            <span className="p2-new text-sm mt-2 mb-6 text-black-700">Sign in to get access to the form.</span>
            <AppButton size={ButtonSize.Medium} onClick={onClickSignInButton}>
                Sign In
            </AppButton>
        </HeaderModalWrapper>
    );
}
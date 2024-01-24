import React from 'react';

import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import HeaderModalWrapper from '@Components/Modals/ModalWrappers/HeaderModalWrapper';

import { useModal } from '@app/components/modal-views/context';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function SignInToFillFormModal() {
    const { closeModal } = useModal();
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    const onClickSignInButton = (event: React.MouseEvent<HTMLButtonElement>) => {
        closeModal();
        router.push({
            pathname: '/login',
            query: {
                type: 'responder',
                workspace_id: workspace.id,
                redirect_to: router.asPath
            }
        });
        // openFullScreenModal('LOGIN_VIEW', { nonClosable: true });
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

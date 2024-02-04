import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import HeaderModalWrapper from '@Components/Modals/ModalWrappers/HeaderModalWrapper';

import { useModal } from '@app/components/modal-views/context';
import { StandardFormDto } from '@app/models/dtos/form';
import { useLogoutMutation } from '@app/store/auth/api';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface ResponderAccountProps {
    form: StandardFormDto;
}

export default function ResponderAccountModal({ form }: ResponderAccountProps) {
    const { closeModal } = useModal();
    const router = useRouter();

    const user = useAppSelector(selectAuth);
    const workspace = useAppSelector(selectWorkspace);

    const [trigger] = useLogoutMutation();

    const onClickSwitchAccount = async () => {
        trigger().then(async () => {
            router.push({
                pathname: '/login',
                query: {
                    type: 'responder',
                    workspace_id: workspace.id,
                    redirect_to: router.asPath
                }
            });
        });
    };

    const onClickLogoutAndContinue = async () => {
        trigger().then(() => {
            closeModal();
        });
    };

    return (
        <HeaderModalWrapper headerTitle="Sign In" className="gap-2">
            <span className="mb-6">
                <span className="p2-new text-black-600">Currently signed in as </span> <span className="text-pink-500">{user.email}</span>
            </span>
            <AppButton variant={ButtonVariant.Primary} size={ButtonSize.Medium} onClick={onClickSwitchAccount}>
                Logout and Sign with other email
            </AppButton>
            {!form?.settings?.requireVerifiedIdentity && (
                <AppButton variant={ButtonVariant.Secondary} size={ButtonSize.Medium} onClick={onClickLogoutAndContinue}>
                    Logout and Continue
                </AppButton>
            )}
        </HeaderModalWrapper>
    );
}

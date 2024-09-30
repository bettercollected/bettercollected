import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { invitationConstant } from '@app/constants/locales/invitations';
import { ButtonSize, ButtonVariant } from '@app/Components/Common/Input/Button/AppButtonProps';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { NextSeo } from 'next-seo';
import AuthAccountProfileImage from '../auth/account-profile-image';
import { useTranslation } from 'next-i18next';
import AuthNavbar from '@app/Components/auth/navbar';
import { toast } from '@app/shadcn/components/ui/use-toast';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useRespondToWorkspaceInvitationMutation } from '@app/store/workspaces/members-n-invitations-api';
import { useState } from 'react';
import { useRouter } from 'node_modules/next/router';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { WorkspaceInvitationDto } from '@app/models/dtos/WorkspaceMembersDto';

interface IValidProps {
    workspace: WorkspaceDto;
    invitation: WorkspaceInvitationDto;
}

export default function ValidUser({ workspace, invitation }: IValidProps) {
    const [trigger, { isLoading }] = useRespondToWorkspaceInvitationMutation();
    const { workspaceName } = useAppSelector(selectWorkspace);
    const { t } = useTranslation();
    const [rejected, setRejected] = useState(false);
    const router = useRouter();

    const onAccept = async () => {
        await handleResponse('ACCEPTED');
    };
    const onDecline = async () => {
        await handleResponse('REJECTED');
    };

    const handleResponse = async (status: string) => {
        const request = {
            workspaceId: workspace.id,
            invitationToken: invitation.invitationToken,
            responseStatus: status
        };
        const response: any = await trigger(request);

        if (response.data) {
            if (status === 'REJECTED') {
                setRejected(true);
                setTimeout(() => {
                    window.close();
                }, 2000);
            } else {
                await router.push(`/${workspace.workspaceName}/dashboard`);
            }
        }

        if (response.error) {
            toast({
                title: t(toastMessage.somethingWentWrong),
                description: response.error?.data || t('An unknown error occurred'), // Fallback description
                type: 'foreground' // Change this to a valid type according to your toast implementation
            });
        }
    };

    return (
        <div className=" w-full px-4 py-10">
            <NextSeo title={t(invitationConstant.title) + ' | ' + workspaceName} noindex={true} nofollow={true} />;
            <AuthNavbar showHamburgerIcon={false} showPlans={false} />
            <div className="mt-36 flex w-full flex-col items-center rounded ">
                <div className="flex flex-col md:max-w-[620px]">
                    <div className="flex flex-col items-center justify-center rounded bg-white p-10 md:max-w-[620px]">
                        <AuthAccountProfileImage size={60} image={workspace?.profileImage} name={workspace?.title} />
                        <div className="sh3 !text-black-700 mb-4 mt-6 text-center text-2xl !font-normal ">
                            {t(invitationConstant.title1)}
                            <span className="text-black-900 font-bold">{' ' + workspace?.title || t(localesCommon.untitled)}</span>
                        </div>
                        <div className="body3 !text-black-700 mb-10">{t(invitationConstant.title2)}</div>
                        <div className="flex flex-col items-center space-y-4">
                            <div className="flex flex-col items-center justify-between gap-5 sm:flex-row">
                                <AppButton disabled={isLoading} size={ButtonSize.Big} onClick={onAccept}>
                                    {t(buttonConstant.joinWorkspace)}
                                </AppButton>
                                <AppButton variant={ButtonVariant.Secondary} disabled={isLoading} size={ButtonSize.Big} onClick={onDecline}>
                                    {t(buttonConstant.decline)}
                                </AppButton>
                            </div>
                        </div>
                        <div className="body3 !text-black-700 mt-5">{t(invitationConstant.expiryLink)}</div>
                    </div>
                    <div className="ml-10 mt-8">
                        <div className="body1 mb-6">{t(invitationConstant.list.title)}</div>

                        <ul className="body2 flex list-disc flex-col space-y-3 pl-10">
                            <li>{t(invitationConstant.list['item1'])}</li>
                            <li>{t(invitationConstant.list['item2'])}</li>
                            <li>{t(invitationConstant.list['item3'])}</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    );
}

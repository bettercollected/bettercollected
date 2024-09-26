import React, { useState } from 'react';
import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import AuthNavbar from '@app/Components/auth/navbar';
import { buttonConstant } from '@app/constants/locales/button';
import { invitationConstant } from '@app/constants/locales/invitations';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { WorkspaceDto, WorkspaceInvitationDto } from '@app/models/dtos/workspaceDto';
import { UserStatus } from '@app/models/dtos/UserStatus';
import { useRespondToWorkspaceInvitationMutation } from '@app/store/workspaces/members-n-invitations-api';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface Props {
    workspace: WorkspaceDto;
    user: UserStatus;
    invitation: WorkspaceInvitationDto;
}

const MainValidUser: React.FC<Props> = ({ workspace, user, invitation }: Props) => {
    const [trigger, { isLoading }] = useRespondToWorkspaceInvitationMutation();
    const { t } = useTranslation();
    const router = useRouter();
    const { workspaceName } = useAppSelector(selectWorkspace);

    const [isSwitchOn, setSwitchOn] = useState(false);

    const toggleSwitch = () => {
        setSwitchOn(!isSwitchOn);
    };

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
                setTimeout(() => {
                    window.close();
                }, 2000);
            } else {
                await router.push(`/${workspace.workspaceName}/dashboard`);
            }
        }
        if (response.error) {
            toast(response.error?.data || t('Something went wrong'), {
                type: 'error'
            });
        }
    };

    return (
        <div className="absolute w-full px-4 py-10">
            <NextSeo title={`${t(invitationConstant.title)} | ${workspaceName}`} noindex={true} nofollow={true} />
            <AuthNavbar showHamburgerIcon={false} showPlans={false} />

            <div className="mt-36 flex w-full flex-col items-center rounded">
                <div className="flex flex-col md:max-w-[620px]">
                    <div className="flex flex-col items-center justify-center rounded bg-white p-10 md:max-w-[620px]">
                        <div className="sh3 !text-black-700 mb-4 mt-6 text-center text-2xl !font-normal">
                            {t(invitationConstant.title1)}
                            <span className="text-black-900 font-bold">{` ${workspace?.title || 'Untitled'}`}</span>
                        </div>
                        <div className="body3 !text-black-700 mb-10">{t(invitationConstant.title2)}</div>

                        <div className="mb-4">
                            <button className={`rounded-md px-4 py-2 text-white ${isSwitchOn ? 'bg-blue-500' : 'bg-gray-500'}`} onClick={toggleSwitch}>
                                {isSwitchOn ? 'Switch is ON' : 'Switch is OFF'}
                            </button>
                        </div>

                        <div className="flex flex-col items-center space-y-4">
                            <div className="flex flex-col items-center justify-between gap-5 sm:flex-row">
                                <AppButton disabled={isLoading} size={ButtonSize.Big} onClick={onAccept}>
                                    {t(buttonConstant.joinWorkspace)}
                                </AppButton>
                                <AppButton variant={ButtonVariant.Secondary} disabled={isLoading} size={ButtonSize.Big} onClick={onDecline}>
                                    {t(buttonConstant.decline)}
                                </AppButton>
                            </div>
                            <div className="body3 !text-black-700 mt-5">{t(invitationConstant.expiryLink)}</div>
                        </div>
                    </div>
                    <div className="ml-10 mt-8">
                        <div className="body1 mb-6">{t(invitationConstant.list.title)}</div>
                        <ul className="body2 flex list-disc flex-col space-y-3 pl-5">
                            <li>{t(invitationConstant.list.item1)}</li>
                            <li>{t(invitationConstant.list.item2)}</li>
                            <li>{t(invitationConstant.list.item3)}</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MainValidUser;

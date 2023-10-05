import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import AuthNavbar from '@app/components/auth/navbar';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { invitationConstant } from '@app/constants/locales/invitations';
import { toastMessage } from '@app/constants/locales/toast-message';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { UserStatus } from '@app/models/dtos/UserStatus';
import { WorkspaceInvitationDto } from '@app/models/dtos/WorkspaceMembersDto';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import Login from '@app/pages/login';
import { useAppSelector } from '@app/store/hooks';
import { useRespondToWorkspaceInvitationMutation } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export default function Id({ workspace, user, invitation }: { workspace: WorkspaceDto; user: UserStatus; invitation: WorkspaceInvitationDto }) {
    const [trigger, { isLoading }] = useRespondToWorkspaceInvitationMutation();
    const { t } = useTranslation();
    const [rejected, setRejected] = useState(false);
    const router = useRouter();
    const { workspaceName } = useAppSelector(selectWorkspace);

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
            if (status == 'REJECTED') {
                setRejected(true);
                setTimeout(() => {
                    window.close();
                }, 2000);
            } else {
                await router.push(`/${workspace.workspaceName}/dashboard`);
            }
        }
        if (response.error) {
            toast(response.error?.data || t(toastMessage.somethingWentWrong), {
                type: 'error'
            });
        }
    };

    if (!user) {
        return (
            <>
                <Login />
            </>
        );
    }

    if (rejected) {
        return (
            <div className=" py-10 flex items-center flex-col">
                <NextSeo title={t(invitationConstant.title) + ' | ' + workspaceName} noindex={true} nofollow={true} />;
                <AuthNavbar showHamburgerIcon={false} showPlans={false} />
                <div className="rounded-lg bg-white mt-36  flex flex-col items-center w-full p-10 md:max-w-[502px]">Request Rejected</div>
            </div>
        );
    }

    if (!invitation) {
        return (
            <div className=" py-10 flex items-center flex-col">
                <NextSeo title={t(invitationConstant.title) + ' | ' + workspaceName} noindex={true} nofollow={true} />;
                <AuthNavbar showHamburgerIcon={false} showPlans={false} />
                <div className="rounded-lg bg-white mt-36  flex flex-col items-center w-full p-10 md:max-w-[620px]">{t(workspaceConstant.invitationNotFound)}</div>
            </div>
        );
    }

    return (
        <div className=" py-10 px-4 w-full">
            <NextSeo title={t(invitationConstant.title) + ' | ' + workspaceName} noindex={true} nofollow={true} />;
            <AuthNavbar showHamburgerIcon={false} showPlans={false} />
            <div className="rounded w-full mt-36 flex flex-col items-center ">
                <div className="md:max-w-[620px] flex flex-col">
                    <div className="bg-white md:max-w-[620px] flex flex-col rounded p-10 items-center justify-center">
                        <AuthAccountProfileImage size={60} image={workspace?.profileImage} name={workspace?.title} />
                        <div className="text-2xl text-center mt-6 mb-4 sh3 !font-normal !text-black-700 ">
                            {t(invitationConstant.title1)}
                            <span className="font-bold text-black-900">{' ' + workspace?.title || t(localesCommon.untitled)}</span>
                        </div>
                        <div className="body3 mb-10 !text-black-700">{t(invitationConstant.title2)}</div>
                        <div className="flex flex-col space-y-4 items-center">
                            <div className="flex sm:flex-row flex-col gap-5 justify-between items-center">
                                <AppButton disabled={isLoading} size={ButtonSize.Big} onClick={onAccept}>
                                    {t(buttonConstant.joinWorkspace)}
                                </AppButton>
                                <AppButton variant={ButtonVariant.Secondary} disabled={isLoading} size={ButtonSize.Big} onClick={onDecline}>
                                    {t(buttonConstant.decline)}
                                </AppButton>
                            </div>
                        </div>
                        <div className="mt-5 body3 !text-black-700">{t(invitationConstant.expiryLink)}</div>
                    </div>
                    <div className="ml-10 mt-8">
                        <div className="body1 mb-6">{t(invitationConstant.list.title)}</div>

                        <ul className="list-disc body2 flex flex-col space-y-3 pl-10">
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

export async function getServerSideProps(_context: any) {
    const { id } = _context.query;
    const config = getServerSideAuthHeaderConfig(_context);
    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(_context)).props;
    let user = null;
    let invitation = null;
    try {
        const userStatus = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, config);
        user = (await userStatus?.json().catch((e: any) => e)) ?? null;
        if (userStatus.status !== 200)
            return {
                props: {
                    ...globalProps
                }
            };
        if (user !== null) {
            const invitation_response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/${globalProps.workspace.id}/members/invitations/${id}`, config);
            invitation = await invitation_response?.json();
            if (invitation_response.status !== 200 || user?.email !== invitation?.email) {
                return {
                    props: {
                        ...globalProps,
                        user: user
                    }
                };
            }
        }
    } catch (e) {
        return {
            notFound: true
        };
    }

    return {
        props: {
            ...globalProps,
            user: user,
            invitation: invitation
        }
    };
}

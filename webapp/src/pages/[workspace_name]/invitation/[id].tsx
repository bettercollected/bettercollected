import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import AuthNavbar from '@app/components/auth/navbar';
import Button from '@app/components/ui/button';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { invitationConstant } from '@app/constants/locales/invitations';
import { toastMessage } from '@app/constants/locales/toast-message';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import Login from '@app/pages/login';
import { useRespondToWorkspaceInvitationMutation } from '@app/store/workspaces/members-n-invitations-api';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export default function Id({ workspace, user, invitation }: { workspace: WorkspaceDto; user: any; invitation: any }) {
    const [trigger, { isLoading }] = useRespondToWorkspaceInvitationMutation();
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
            invitationToken: invitation.invitation_token,
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
                <AuthNavbar showHamburgerIcon={false} showPlans={false} />
                <div className="rounded-lg bg-white mt-14  flex flex-col items-center w-full p-10 md:max-w-[502px]">Request Rejected</div>
            </div>
        );
    }

    if (!invitation) {
        return (
            <div className=" py-10 flex items-center flex-col">
                <AuthNavbar showHamburgerIcon={false} showPlans={false} />
                <div className="rounded-lg bg-white mt-14  flex flex-col items-center w-full p-10 md:max-w-[620px]">{t(workspaceConstant.invitationNotFound)}</div>
            </div>
        );
    }

    return (
        <div className=" py-10 px-4 w-full">
            <AuthNavbar showHamburgerIcon={false} showPlans={false} />
            <div className="rounded w-full mt-[68px] flex flex-col items-center ">
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
                                <Button disabled={isLoading} className="w-full sm:w-fit" size="large" onClick={onAccept}>
                                    {t(buttonConstant.joinWorkspace)}
                                </Button>
                                <Button className="w-full sm:w-fit text-white bg-black-500 hover:!bg-black-600" disabled={isLoading} size="large" onClick={onDecline}>
                                    {t(buttonConstant.decline)}
                                </Button>
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

        user = (await userStatus?.json().catch((e: any) => e))?.user ?? null;
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

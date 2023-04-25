import React, { useState } from 'react';

import Image from 'next/image';
import { useRouter } from 'next/router';

import _ from 'lodash';

import { toast } from 'react-toastify';

import AuthNavbar from '@app/components/auth/navbar';
import Button from '@app/components/ui/button';
import MarkdownText from '@app/components/ui/markdown-text';
import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import Login from '@app/pages/login';
import { useRespondToWorkspaceInvitationMutation } from '@app/store/workspaces/members-n-invitations-api';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export default function Id({ workspace, user, invitation }: { workspace: WorkspaceDto; user: any; invitation: any }) {
    const profileName = _.capitalize(user?.first_name) + ' ' + _.capitalize(user?.last_name);

    const [trigger, { isLoading }] = useRespondToWorkspaceInvitationMutation();

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
            } else {
                await router.push(`/${workspace.workspaceName}/dashboard`);
            }
        }
        if (response.error) {
            toast('Something went wrong.', {
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
                <div className="rounded mt-14 border flex flex-col items-center w-full border-gray-200 p-10 lg:max-w-[800px]">Request Rejected</div>
            </div>
        );
    }

    return (
        <div className=" py-10 flex items-center flex-col">
            <AuthNavbar showHamburgerIcon={false} showPlans={false} />
            <div className="rounded mt-[68px] border flex flex-col items-center w-full border-gray-200 p-10 lg:max-w-[800px]">
                {!invitation ? (
                    <div className="w-full h-full flex items-center justify-center">Invitation not Found</div>
                ) : (
                    <>
                        <div className="flex rounded-full  items-center justify-center mr-2 bg-blue-50">
                            {workspace?.profileImage ? <Image alt={workspace?.title} src={workspace.profileImage || ''} className="rounded-full" width={64} height={64} /> : <>{profileName[0]?.toUpperCase()}</>}
                        </div>
                        <div className="text-2xl font-bold">{workspace?.title || 'Untitled'}</div>
                        <MarkdownText description={workspace.description} contentStripLength={100} markdownClassName="pt-3 md:pt-7 text-base text-grey" textClassName="text-base" />

                        <div className="flex flex-col space-y-4 items-center">
                            <div className="text-xl">You have been invited to join this workspace!</div>
                            <div className="flex space-x-8">
                                <Button disabled={isLoading} size="small" onClick={onAccept}>
                                    Accept
                                </Button>
                                <Button disabled={isLoading} size="small" onClick={onDecline}>
                                    Decline
                                </Button>
                            </div>
                        </div>
                    </>
                )}
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
        const userStatus = await fetch(`${environments.API_ENDPOINT_HOST}/auth/status`, config);
        user = (await userStatus?.json().catch((e: any) => e))?.user ?? null;
        if (user !== null) {
            const invitation_response = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${globalProps.workspace.id}/members/invitations/${id}`, config);
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

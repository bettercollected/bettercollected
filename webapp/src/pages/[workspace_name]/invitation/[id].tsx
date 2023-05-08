import React, { useState } from 'react';

import Image from 'next/image';
import { useRouter } from 'next/router';

import _ from 'lodash';

import { toast } from 'react-toastify';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
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
                setTimeout(() => {
                    window.close();
                }, 2000);
            } else {
                await router.push(`/${workspace.workspaceName}/dashboard`);
            }
        }
        if (response.error) {
            toast(response.error?.data || 'Something went wrong.', {
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
                <div className="rounded-lg bg-white mt-14  flex flex-col items-center w-full p-10 md:max-w-[502px]">Invitation Not Found</div>
            </div>
        );
    }

    return (
        <div className=" py-10 px-5 w-full">
            <AuthNavbar showHamburgerIcon={false} showPlans={false} />
            <div className="rounded w-full mt-[68px] flex flex-col items-center ">
                <div className="md:max-w-[502px] flex flex-col">
                    <div className="bg-white md:max-w-[502px] flex flex-col rounded p-10 items-center justify-center">
                        <AuthAccountProfileImage size={60} image={workspace?.profileImage} name={workspace?.workspaceName} />
                        <div className="text-2xl mt-6 mb-4 sh3 !font-normal !text-black-700 ">
                            You have been invited to
                            <span className="font-bold text-black-900">{' ' + workspace?.title || 'Untitled'}</span>
                        </div>
                        <div className="body3 mb-10 !text-black-700">Join workspace and start collaborating</div>
                        <div className="flex flex-col space-y-4 items-center">
                            <div className="flex space-x-5">
                                <Button disabled={isLoading} size="large" onClick={onAccept}>
                                    Join Workspace
                                </Button>
                                <Button className="text-white bg-black-500 hover:!bg-black-600" disabled={isLoading} size="large" onClick={onDecline}>
                                    Decline
                                </Button>
                            </div>
                        </div>
                        <div className="mt-5 body3 !text-black-700">This link will expire in 7 days.</div>
                    </div>
                    <div className="ml-10 mt-8">
                        <div className="body1 mb-6">You will have access to:</div>

                        <ul className="list-disc body2 flex flex-col space-y-3 pl-10">
                            <li>All forms and responses in workspace</li>
                            <li>Importing forms to workspace</li>
                            <li>Deleting form form workspace</li>
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

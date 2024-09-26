import React, { useState } from 'react';
import { NextSeo } from 'next-seo';
import AuthNavbar from '@app/Components/auth/navbar';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { toast } from 'react-toastify';
import { FaCheckCircle } from 'react-icons/fa';
import environments from '@app/configs/environments';

interface Props {
    invitation: {
        invitationToken: string;
        email: string;
    };
    workspaceId: string;
}

export default function InvalidUserInvitation({ invitation, workspaceId }: Props) {
    const { workspaceName } = useAppSelector(selectWorkspace);
    const [invitationSent, setInvitationSent] = useState(false);
    const [loading, setLoading] = useState(false);

    const resendInvitation = async () => {
        setLoading(true);
        try {
            const response = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${workspaceId}/members/invitations/${invitation.invitationToken}/resend`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    accept: 'application/json'
                },
                credentials: 'include'
            });

            if (response.ok) {
                toast.success('Invitation resent successfully!');
                setInvitationSent(true);
            } else {
                const errorText = await response.text();
                throw new Error(errorText || 'Failed to resend invitation');
            }
        } catch (error: any) {
            toast.error(`Error resending invitation: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-gray-100">
            <NextSeo title={`Invalid Invitation | ${workspaceName}`} noindex={true} nofollow={true} />
            <AuthNavbar showHamburgerIcon={false} showPlans={false} />
            <div
                className="mx-4 flex w-full flex-col items-center rounded-lg bg-white p-10 shadow-sm md:max-w-[500px]"
                style={{
                    boxShadow: '0 8px 10px -16px rgba(0, 0, 0, 0.3), 0 4px 6px rgba(0.1, 0.1, 0.1, 0)'
                }}
            >
                <div className="text-black-900 mb-4 text-center text-xl font-semibold">Invalid Invitation</div>
                <p className="text-center text-base text-red-600">Oops! It seems like you don&apost have access to this invitation.</p>
                <p className="mt-4 text-center text-sm text-gray-600">
                    The invitation was sent to <strong>{invitation.email}</strong>. If you believe this is an error, please request a new invitation.
                </p>

                <div className="mt-6 flex items-center">
                    <button onClick={resendInvitation} className={`rounded bg-blue-500 px-4 py-2 text-white transition-colors hover:bg-blue-600 ${invitationSent ? 'cursor-not-allowed bg-gray-400' : ''}`} disabled={invitationSent || loading}>
                        {loading ? 'Resending...' : invitationSent ? 'Invitation Sent' : 'Resend Invitation'}
                    </button>

                    {invitationSent && <FaCheckCircle className="ml-3 text-green-500" size={24} />}
                </div>
            </div>
        </div>
    );
}

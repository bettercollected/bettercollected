import { useTranslation } from 'react-i18next';
import { useRouter } from 'next/navigation';
import React, { useState } from 'react';

import AuthNavbar from '@app/components/auth/auth-navbar';
import { buttonConstant } from '@app/constants/locales/button';
import { invitationConstant } from '@app/constants/locales/invitations';
import { UserStatus } from '@app/models/dtos/user-status';
import { WorkspaceDto, WorkspaceInvitationDto } from '@app/models/dtos/workspace-dto';
import { PAGE_CARD } from '@app/components/ui/page-surface';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { useRespondToWorkspaceInvitationMutation } from '@app/store/workspaces/members-n-invitations-api';
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
    const { toast } = useToast();
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
            toast({
                description: response.error?.data || t('Something went wrong'),
                variant: 'destructive'
            });
        }
    };

    return (
        <div className="min-h-screen w-full">
            <AuthNavbar showHamburgerIcon={false} showPlans={false} />

            <div className="mx-auto flex w-full max-w-[620px] flex-col px-4 pb-10 pt-12 sm:pt-20">
                <div className={cn(PAGE_CARD, 'flex flex-col sm:p-10')}>
                    <div className="flex flex-col items-center justify-center">
                        <div className="sh3 text-black-700! mb-4 mt-6 text-center text-2xl font-normal!">
                            {t(invitationConstant.title1)}
                            <span className="text-black-900 font-bold">{` ${workspace?.title || 'Untitled'}`}</span>
                        </div>
                        <div className="body3 text-black-700! mb-10">{t(invitationConstant.title2)}</div>

                        <div className="mb-4">
                            <button className={`rounded-md px-4 py-2 text-white ${isSwitchOn ? 'bg-blue-500' : 'bg-gray-500'}`} onClick={toggleSwitch}>
                                {isSwitchOn ? 'Switch is ON' : 'Switch is OFF'}
                            </button>
                        </div>

                        <div className="flex flex-col items-center space-y-4">
                            <div className="flex flex-col items-center justify-between gap-5 sm:flex-row">
                                <Button disabled={isLoading} size="lg" onClick={onAccept}>
                                    {t(buttonConstant.joinWorkspace)}
                                </Button>
                                <Button variant="secondary" disabled={isLoading} size="lg" onClick={onDecline}>
                                    {t(buttonConstant.decline)}
                                </Button>
                            </div>
                            <div className="body3 text-black-700! mt-5">{t(invitationConstant.expiryLink)}</div>
                        </div>
                    </div>
                    <div className="mt-8 border-t border-hairline-strong pt-6">
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

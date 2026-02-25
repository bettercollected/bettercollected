import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import { Info } from 'lucide-react';
import DataTable from 'react-data-table-component';

import { dataTableCustomStyles } from '@Components/datatable/datatable-styles';
import MemberOptions from '@Components/datatable/member-options';
import StatusBadge from '@app/components/badge/status-badge';
import { localesCommon } from '@app/constants/locales/common';
import { members } from '@app/constants/locales/members';
import { toastMessage } from '@app/constants/locales/toast-message';
import { WorkspaceInvitationDto } from '@app/models/dtos/WorkspaceMembersDto';
import { Page } from '@app/models/dtos/page';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { useInviteToWorkspaceMutation } from '@app/store/workspaces/members-n-invitations-api';
import { utcToLocalDate, utcToLocalTime } from '@app/utils/dateUtils';

interface IInvitationTableProps {
    data: Page<WorkspaceInvitationDto>;
}

export default function InvitationsTable({ data }: IInvitationTableProps) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const [trigger] = useInviteToWorkspaceMutation();
    const [invitations, setInvitations] = useState<Array<any>>([]);
    const workspace = useAppSelector((state) => state.workspace);

    useEffect(() => {
        if (data && data.items && Array.isArray(data.items)) setInvitations(data.items);
    }, [data]);

    const EmptyPendingRequest = () => (
        <div className="my-16 flex flex-col items-center gap-6">
            <Info className="h-8 w-8" />
            <p className="body2"> {t(members.pendingRequests.empty)}</p>
        </div>
    );
    const handleInvitation = async ({ email }: { email: string }) => {
        try {
            await trigger({
                workspaceId: workspace.id,
                body: {
                    role: 'COLLABORATOR',
                    email: email
                }
            });
            toast({ description: t(toastMessage.invitationSent).toString() });
        } catch (error) {
            toast({ description: t(toastMessage.failedToSentEmail).toString(), variant: 'destructive' });
        }
    };

    const Status = ({ status, email }: { status: string; email: string }) => {
        return (
            <div className="flex items-center gap-5">
                <StatusBadge status={status} />
                {status.toLowerCase() === 'expired' && (
                    <div className="truncate">
                        <span className="body4 !text-brand-500 cursor-pointer" onClick={() => handleInvitation({ email })}>
                            Resend Invitation
                        </span>
                    </div>
                )}
            </div>
        );
    };
    const dataTableResponseColumns: any = [
        {
            name: t(members.member),
            selector: (invitation: WorkspaceInvitationDto) => invitation.email,
            minWidth: '300px',
            style: {
                color: '#202124',
                fontSize: '16px',
                fontWeight: 500,
                paddingLeft: '16px',
                paddingRight: '16px',
                overflow: 'auto'
            }
        },
        {
            name: t(members.invitationDate),
            selector: (invitation: WorkspaceInvitationDto) => (!!invitation?.createdAt ? `${utcToLocalDate(invitation?.createdAt)} ${utcToLocalTime(invitation?.createdAt)}` : ''),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },

        {
            name: t(localesCommon.status),
            selector: (invitation: WorkspaceInvitationDto) =>
                Status({
                    status: invitation.invitationStatus,
                    email: invitation.email
                }),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },

        {
            cell: (invitation: WorkspaceInvitationDto) => (invitation.invitationStatus === 'PENDING' ? <MemberOptions invitation={invitation} workspaceId={workspace.id} /> : ''),
            allowOverflow: true,
            button: true,
            width: '60px',
            style: {
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        }
    ];
    if (invitations && invitations.length > 0)
        return (
            <>
                <DataTable className="mt-2 !overflow-auto p-0" columns={dataTableResponseColumns} data={invitations || []} customStyles={dataTableCustomStyles} highlightOnHover={false} pointerOnHover={false} />
            </>
        );
    return EmptyPendingRequest();
}

import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import InfoCircle from '@Components/Common/Icons/InfoCircle';
import { Typography } from '@mui/material';
import DataTable from 'react-data-table-component';
import { toast } from 'react-toastify';

import StatusBadge from '@app/components/badge/status-badge';
import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import MemberOptions from '@app/components/datatable/workspace-settings/member-options';
import { localesCommon } from '@app/constants/locales/common';
import { members } from '@app/constants/locales/members';
import { toastMessage } from '@app/constants/locales/toast-message';
import { WorkspaceInvitationDto } from '@app/models/dtos/WorkspaceMembersDto';
import { Page } from '@app/models/dtos/page';
import { useAppSelector } from '@app/store/hooks';
import { useInviteToWorkspaceMutation } from '@app/store/workspaces/members-n-invitations-api';
import { parseDateStrToDate, toHourMinStr, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';

interface IInvitationTableProps {
    data: Page<WorkspaceInvitationDto>;
}

export default function InvitationsTable({ data }: IInvitationTableProps) {
    const { t } = useTranslation();
    const [trigger] = useInviteToWorkspaceMutation();
    const [invitations, setInvitations] = useState<Array<any>>([]);
    const workspace = useAppSelector((state) => state.workspace);

    useEffect(() => {
        if (data && data.items && Array.isArray(data.items)) setInvitations(data.items);
    }, [data]);

    const EmptyPendingRequest = () => (
        <div className="my-16 flex flex-col gap-6 items-center">
            <InfoCircle className="h-8 w-8" />
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
            }).unwrap();
            toast(t(toastMessage.invitationSent).toString(), { type: 'success' });
        } catch (error) {
            toast(t(toastMessage.failedToSentEmail).toString(), { type: 'error' });
        }
    };

    const Status = ({ status, email }: { status: string; email: string }) => {
        return (
            <div className="flex gap-5 items-center">
                <StatusBadge status={status} />
                {status.toLowerCase() === 'expired' && (
                    <Typography noWrap>
                        <span className="body4 cursor-pointer !text-brand-500" onClick={() => handleInvitation({ email })}>
                            Resend Invitation
                        </span>
                    </Typography>
                )}
            </div>
        );
    };
    const dataTableResponseColumns: any = [
        {
            name: t(members.member),
            selector: (invitation: WorkspaceInvitationDto) => invitation.email,
            grow: 2,
            style: {
                color: '#202124',
                fontSize: '16px',
                fontWeight: 500,
                marginLeft: '-5px',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: t(members.invitationDate),
            selector: (invitation: WorkspaceInvitationDto) => (!!invitation?.createdAt ? `${toMonthDateYearStr(parseDateStrToDate(utcToLocalDate(invitation?.createdAt)))} ${toHourMinStr(parseDateStrToDate(utcToLocalDate(invitation?.createdAt)))}` : ''),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },

        {
            name: t(localesCommon.status),
            selector: (invitation: WorkspaceInvitationDto) => Status({ status: invitation.invitationStatus, email: invitation.email }),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },

        {
            cell: (invitation: WorkspaceInvitationDto) => (invitation.invitationStatus === 'PENDING' ? <MemberOptions invitation={invitation} /> : ''),
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
                <DataTable className="p-0 mt-2 !overflow-auto" columns={dataTableResponseColumns} data={invitations || []} customStyles={dataTableCustomStyles} highlightOnHover={false} pointerOnHover={false} />
            </>
        );
    return EmptyPendingRequest();
}

import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import _ from 'lodash';

import { Typography } from '@mui/material';
import DataTable from 'react-data-table-component';
import { toast } from 'react-toastify';

import StatusBadge from '@app/components/badge/status-badge';
import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import MemberOptions from '@app/components/datatable/workspace-settings/member-options';
import { localesGlobal } from '@app/constants/locales/global';
import { members } from '@app/constants/locales/members';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useAppSelector } from '@app/store/hooks';
import { useInviteToWorkspaceMutation } from '@app/store/workspaces/members-n-invitations-api';
import { parseDateStrToDate, toHourMinStr, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';

export default function InvitationsTable({ data }: any) {
    const { t } = useTranslation();
    const [trigger] = useInviteToWorkspaceMutation();
    const [invitations, setInvitations] = useState<Array<any>>([]);
    const workspace = useAppSelector((state) => state.workspace);

    useEffect(() => {
        if (data && data.items && Array.isArray(data.items)) setInvitations(data.items);
    }, [data]);

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
            selector: (invitation: any) => invitation.email,
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
            selector: (invitation: any) => (!!invitation?.created_at ? `${toMonthDateYearStr(parseDateStrToDate(utcToLocalDate(invitation?.created_at)))} ${toHourMinStr(parseDateStrToDate(utcToLocalDate(invitation?.created_at)))}` : ''),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },

        {
            name: t(localesGlobal.status),
            selector: (invitation: any) => Status({ status: invitation.invitation_status, email: invitation.email }),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },

        {
            cell: (invitation: any) => (invitation.invitation_status === 'PENDING' ? <MemberOptions invitation={invitation} /> : ''),
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

    return (
        <>
            <DataTable className="p-0 mt-2 !overflow-auto" columns={dataTableResponseColumns} data={invitations || []} customStyles={dataTableCustomStyles} highlightOnHover={false} pointerOnHover={false} />
        </>
    );
}

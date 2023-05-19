import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import _ from 'lodash';

import DataTable from 'react-data-table-component';

import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import MemberOptions from '@app/components/datatable/workspace-settings/member-options';
import { localesGlobal } from '@app/constants/locales/global';
import { members } from '@app/constants/locales/members';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersInvitationsQuery } from '@app/store/workspaces/members-n-invitations-api';
import { parseDateStrToDate, toHourMinStr, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';

export default function InvitationsTable() {
    const { t } = useTranslation();
    const workspace = useAppSelector((state) => state.workspace);
    const { data, isLoading } = useGetWorkspaceMembersInvitationsQuery({ workspaceId: workspace.id });
    const [invitations, setInvitations] = useState<Array<any>>([]);

    useEffect(() => {
        if (data && data.items && Array.isArray(data.items)) setInvitations(data.items);
    }, [data]);

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
            name: t(members.role),
            selector: (invitation: any) => _.capitalize(invitation.role),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                fontSize: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: t(localesGlobal.status),
            selector: (invitation: any) => _.capitalize(invitation.invitation_status),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
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
            <DataTable className="p-0 mt-2" columns={dataTableResponseColumns} data={invitations || []} customStyles={dataTableCustomStyles} highlightOnHover={false} pointerOnHover={false} />
        </>
    );
}

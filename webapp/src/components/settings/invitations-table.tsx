import React, { useEffect, useState } from 'react';

import _ from 'lodash';

import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import DataTable from 'react-data-table-component';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import MemberOptions from '@app/components/datatable/workspace-settings/member-options';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersInvitationsQuery, useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';
import { parseDateStrToDate, toHourMinStr, toLocaleString, toLocaleStringFromDateString, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';
import { getFullNameFromUser } from '@app/utils/userUtils';

export default function InvitationsTable() {
    const workspace = useAppSelector((state) => state.workspace);
    const { data, isLoading } = useGetWorkspaceMembersInvitationsQuery({ workspaceId: workspace.id });
    const [invitations, setInvitations] = useState<Array<any>>([]);

    useEffect(() => {
        if (data && data.items && Array.isArray(data.items)) setInvitations(data.items);
    }, [data]);

    const dataTableResponseColumns: any = [
        {
            name: 'Member',
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
            name: 'Role',
            selector: (invitation: any) => _.capitalize(invitation.role),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                fontSize: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: 'Status',
            selector: (invitation: any) => _.capitalize(invitation.invitation_status),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },
        {
            name: 'Invitation Date',
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

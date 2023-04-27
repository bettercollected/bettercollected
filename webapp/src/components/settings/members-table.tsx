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
import FormOptionsDropdownMenu from '@app/components/datatable/form/form-options-dropdown';
import MemberOptions from '@app/components/datatable/workspace-settings/member-options';
import { StandardFormDto } from '@app/models/dtos/form';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';
import { parseDateStrToDate, toHourMinStr, toLocaleStringFromDateString, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';
import { getFullNameFromUser } from '@app/utils/userUtils';

export default function MembersTable() {
    const workspace = useAppSelector((state) => state.workspace);
    const { data, isLoading } = useGetWorkspaceMembersQuery({ workspaceId: workspace.id });
    const [members, setMembers] = useState<Array<any>>([]);

    useEffect(() => {
        if (data && Array.isArray(data)) setMembers(data);
    }, [data]);

    const dataTableResponseColumns: any = [
        {
            name: 'Member',
            selector: (member: any) => (
                <div className="flex space-x-4">
                    <AuthAccountProfileImage image={member.profile_image} name={getFullNameFromUser(member)} size={40} />
                    <div className="flex flex-col">
                        <div className="!body3">{getFullNameFromUser(member)}</div>
                        <div className="!body5 !text-black-600">{member.email}</div>
                    </div>
                </div>
            ),
            grow: 2,
            style: {
                color: '#202124',
                fontSize: '14px',
                fontWeight: 500,
                marginLeft: '-5px',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: 'Role',
            selector: (member: any) => _.capitalize(member.roles[0]),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: 'Joined',
            selector: (member: any) => (!!member?.joined ? `${toMonthDateYearStr(parseDateStrToDate(utcToLocalDate(member?.joined)))} ${toHourMinStr(parseDateStrToDate(utcToLocalDate(member?.joined)))}` : ''),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            cell: (member: any) => <MemberOptions member={member} />,
            allowOverflow: true,
            button: true,
            width: '60px',
            style: {
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        }
    ];

    return (
        <>
            <DataTable className="p-0 mt-2" columns={dataTableResponseColumns} data={data || []} customStyles={dataTableCustomStyles} highlightOnHover={false} pointerOnHover={false} />
        </>
    );
}

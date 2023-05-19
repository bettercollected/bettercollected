import React from 'react';

import { useTranslation } from 'next-i18next';

import _ from 'lodash';

import UserDetails from '@Components/Common/DataDisplay/UserDetails';
import DataTable from 'react-data-table-component';

import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import MemberOptions from '@app/components/datatable/workspace-settings/member-options';
import { members } from '@app/constants/locales/members';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';
import { parseDateStrToDate, toHourMinStr, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';

export default function MembersTable() {
    const workspace = useAppSelector((state) => state.workspace);
    const { data, isLoading } = useGetWorkspaceMembersQuery({ workspaceId: workspace.id });
    // const [members, setMembers] = useState<Array<any>>([]);
    const { t } = useTranslation();

    // useEffect(() => {
    //     if (data && Array.isArray(data)) setMembers(data);
    // }, [data]);

    const dataTableResponseColumns: any = [
        {
            selector: (member: any) => <UserDetails user={member} />,
            name: t(members.member),
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
            name: t(members.role),
            selector: (member: any) => _.capitalize(member.roles[0]),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },
        {
            name: t(members.join),
            selector: (member: any) => (!!member?.joined ? `${toMonthDateYearStr(parseDateStrToDate(utcToLocalDate(member?.joined)))} ${toHourMinStr(parseDateStrToDate(utcToLocalDate(member?.joined)))}` : ''),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },
        {
            cell: (member: any) => workspace?.ownerId !== member.id && <MemberOptions member={member} />,
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

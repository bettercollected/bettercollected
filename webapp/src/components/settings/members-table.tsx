import _ from 'lodash';

import UserDetails from '@Components/common/user-details';
import { dataTableCustomStyles } from '@Components/datatable/datatable-styles';
import MemberOptions from '@Components/datatable/member-options';
import DataTable from 'react-data-table-component';
import { useTranslation } from 'react-i18next';

import { members } from '@app/constants/locales/members';
import { useAppSelector } from '@app/store/hooks';
import { utcToLocalDate, utcToLocalTime } from '@app/utils/date-utils';

const customDataTableStyles = { ...dataTableCustomStyles };

customDataTableStyles.rows.style.backgroundColor = 'white';
export default function MembersTable({ data }: any) {
    const workspace = useAppSelector((state) => state.workspace);
    const { t } = useTranslation();

    const dataTableResponseColumns: any = [
        {
            selector: (member: any) => <UserDetails user={member} />,
            name: t(members.member),
            minWidth: '300px',
            style: {
                color: '#101826',
                fontSize: '14px',
                fontWeight: 500,
                paddingLeft: '16px',
                paddingRight: '16px',
                overflow: 'auto hidden'
            }
        },

        {
            name: t(members.join),
            selector: (member: any) => (!!member?.joined ? `${utcToLocalDate(member?.joined)} - ${utcToLocalTime(member?.joined)}` : ''),
            style: {
                color: '#3A465A',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },
        {
            name: t(members.role),
            // A member the SCIM directory manages: the role follows their
            // groups at the identity provider, so it is not changed here.
            cell: (member: any) => (
                <div className="flex flex-col gap-0.5 py-1">
                    <span>{_.capitalize(member.roles[0])}</span>
                    {member.managedByDirectory && (
                        <span className="text-[11px] font-medium text-black-500" data-testid="managed-by-directory">
                            {t(members.managedByDirectory)}
                        </span>
                    )}
                    {member.disabled && <span className="text-[11px] font-medium text-[#C43D3D]">{t(members.deactivated)}</span>}
                </div>
            ),
            style: {
                color: '#3A465A',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },
        {
            cell: (member: any) => workspace?.ownerId !== member.id && <MemberOptions member={member} workspaceId={''} />,
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
            <DataTable className="mt-2 !overflow-auto p-0" columns={dataTableResponseColumns} data={data || []} customStyles={customDataTableStyles} highlightOnHover={false} pointerOnHover={false} />
        </>
    );
}

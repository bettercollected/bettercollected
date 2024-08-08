import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import StyledPagination from '@Components/Common/Pagination';
import SearchInput from '@Components/Common/Search/SearchInput';
import { CheckCircle } from '@mui/icons-material';
import { MenuItem, Typography } from '@mui/material';
import cn from 'classnames';
import DataTable from 'react-data-table-component';

import { dataTableCustomStyles } from '@app/Components/datatable/form/datatable-styles';
import { Close } from '@app/Components/icons/close';
import { Plus } from '@app/Components/icons/plus';
import { useModal } from '@app/Components/modal-views/context';
import EmptyResponse from '@app/Components/ui/empty-response';
import Loader from '@app/Components/ui/loader';
import globalConstants from '@app/constants/global';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { groupConstant } from '@app/constants/locales/group';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { useGroupMember } from '@app/lib/hooks/use-group-members';
import { WorkspaceResponderDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllRespondersGroupQuery, useGetWorkspaceRespondersQuery } from '@app/store/workspaces/api';
import { IGetAllSubmissionsQuery } from '@app/store/workspaces/types';
import { isEmailInGroup } from '@app/utils/groupUtils';

const customStyles = { ...dataTableCustomStyles };
customStyles.rows.style.backgroundColor = 'white';
export default function WorkspaceResponses({ workspace }: { workspace: WorkspaceDto }) {
    const [query, setQuery] = useState<IGetAllSubmissionsQuery>({
        workspaceId: workspace.id,
        page: 1,
        size: globalConstants.pageSize
    });
    const { addMembersOnGroup, removeMemberFromGroup } = useGroupMember();
    const { data, isLoading, isError } = useGetWorkspaceRespondersQuery(query);
    const responderGroupsQuery = useGetAllRespondersGroupQuery(workspace.id);
    const isAdmin = useAppSelector(selectIsAdmin);
    const { openModal } = useModal();
    const { t } = useTranslation();
    const router = useRouter();

    const handlePageChange = (e: any, page: number) => {
        setQuery({ ...query, page: page });
    };

    const AddButton = (onClick?: () => void) => (
        <Tooltip title={!onClick ? t(localesCommon.noGroupFound) : ''}>
            <div onClick={onClick} className={cn('text-black-600 flex items-center  gap-1', !onClick && 'cursor-not-allowed opacity-30')}>
                <Plus className="h-4 w-4 " />
                <p className="body5 !text-black-600">{t(buttonConstant.add)}</p>
            </div>
        </Tooltip>
    );
    const ShowResponderGroups = (email: string) => (
        <div className="flex flex-row flex-wrap gap-1">
            {responderGroupsQuery.data?.map((group: ResponderGroupDto) => {
                if (group.emails?.includes(email))
                    return (
                        <div
                            key={group.id}
                            onClick={() =>
                                openModal('DELETE_CONFIRMATION', {
                                    title: t(localesCommon.remove) + ' ' + group.name,
                                    handleDelete: () => removeMemberFromGroup({ email, group, workspaceId: workspace.id })
                                })
                            }
                            className={cn('bg-brand-200 body5 !text-brand-500 group flex w-fit cursor-pointer items-center gap-2 rounded p-1 leading-none', !isAdmin && 'pointer-events-none')}
                        >
                            <span className="body5 text-black-8000">{group.name}</span>
                            {isAdmin && <Close className="hidden h-2 w-2 group-hover:block " />}
                        </div>
                    );
                return null;
            })}
            {responderGroupsQuery.data && responderGroupsQuery.data?.length === 0 && isAdmin && AddButton()}
            {responderGroupsQuery.data && responderGroupsQuery.data?.filter((group: ResponderGroupDto) => group.emails?.includes(email)).length === 0 && !isAdmin && <p className="body5 text-black-800">{t(groupConstant.notInAnyGroup)}</p>}
            {responderGroupsQuery.data && responderGroupsQuery.data?.length > 0 && isAdmin && (
                <MenuDropdown showExpandMore={false} className="cursor-pointer" width={180} id="group-option" menuTitle={''} menuContent={AddButton(() => {})}>
                    {responderGroupsQuery.data?.map((group: ResponderGroupDto) => (
                        <MenuItem disabled={isEmailInGroup(group, email)} onClick={() => addMembersOnGroup({ email, group, workspaceId: workspace.id })} key={group.id} className="hover:bg-black-200 flex justify-between py-3">
                            <Typography className="body4" noWrap>
                                {group.name}
                            </Typography>
                            {isEmailInGroup(group, email) && <CheckCircle className="text-brand-500 h-5 w-5" />}
                        </MenuItem>
                    ))}
                </MenuDropdown>
            )}
        </div>
    );

    const dataTableResponseColumns: any = [
        {
            name: t(formConstant.responder),
            selector: (responder: WorkspaceResponderDto) => responder.email,
            minWidth: '300px',
            style: {
                color: '#202124',
                fontSize: '14px',
                fontWeight: 500,
                paddingLeft: '16px',
                paddingRight: '16px',
                overflow: 'auto hidden'
            }
        },
        {
            name: t(formConstant.responses),
            selector: (responder: WorkspaceResponderDto) => responder.responses,
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: t(formConstant.deletionRequests),
            selector: (responder: WorkspaceResponderDto) => responder.deletionRequests,
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: t(groupConstant.default),
            selector: (responder: WorkspaceResponderDto) => ShowResponderGroups(responder.email),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        }
    ];

    const handleSearch = (event: any) => {
        if (event.target.value) setQuery({ ...query, email: event.target.value });
        else {
            const { email, ...removedQuery } = query;
            setQuery(removedQuery);
        }
    };

    const Response = () => {
        if (data?.items && data?.items.length > 0)
            return (
                <>
                    <DataTable className="mt-4 !overflow-auto p-0" columns={dataTableResponseColumns} data={data?.items || []} customStyles={customStyles} highlightOnHover={false} pointerOnHover={false} />
                    {Array.isArray(data?.items) && data?.total > globalConstants.pageSize && (
                        <div className="mt-8 flex justify-center">
                            <StyledPagination shape="rounded" count={data?.pages || 0} page={query.page || 1} onChange={handlePageChange} />
                        </div>
                    )}
                </>
            );
        return <EmptyResponse title={t(formConstant.empty.response.title)} description={t(formConstant.empty.response.description)} />;
    };

    if (isLoading && responderGroupsQuery.isLoading) {
        return (
            <div className=" flex w-full justify-center py-10">
                <Loader />
            </div>
        );
    }
    return (
        <>
            <div className="flex flex-col items-start justify-between gap-6 md:flex-row">
                <div>
                    <p className="h3-new font-semibold">
                        {t(workspaceConstant.allResponders)} {data && ' (' + data.total + ')'}{' '}
                    </p>
                    <div className="p2-new text-black-700 mt-2 max-w-[400px]">Below, you will find a list of responders who have filled forms of your workspace.</div>
                </div>
                <div className="w-full md:w-[282px]">
                    <SearchInput handleSearch={handleSearch} />
                </div>
            </div>
            {Response()}
        </>
    );
}

import React, { useEffect, useMemo, useState } from 'react';

import { useTranslation } from 'next-i18next';

import { debounce, escapeRegExp } from 'lodash';

import Divider from '@Components/Common/DataDisplay/Divider';
import { InputAdornment, TextField } from '@mui/material';
import DataTable from 'react-data-table-component';

import { StyledTextField } from '@app/components/dashboard/workspace-forms-tab-content';
import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import FormOptionsDropdownMenu from '@app/components/datatable/form/form-options-dropdown';
import DataTableProviderFormCell from '@app/components/datatable/form/provider-form-cell';
import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import { SearchIcon } from '@app/components/icons/search';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import ActiveLink from '@app/components/ui/links/active-link';
import { formsConstant } from '@app/constants/locales/forms';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetWorkspaceFormsQuery, useSearchWorkspaceFormsMutation } from '@app/store/workspaces/api';
import { parseDateStrToDate, toHourMinStr, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';

export default function FormPage({ workspace, hasCustomDomain }: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const [sortValue, setSortValue] = useState('newest_oldest');
    const [filterValue, setFilterValue] = useState('show_all');
    const { t } = useTranslation();

    const workspaceQuery = {
        workspace_id: workspace.id
    };

    const workspaceForms = useGetWorkspaceFormsQuery<any>(workspaceQuery, { pollingInterval: 30000 });
    const [searchWorkspaceForms] = useSearchWorkspaceFormsMutation();
    const [forms, setForms] = useState<Array<any>>(workspaceForms?.data?.items);
    const selectList = [
        {
            id: 'sort-select-label',
            label: 'Sort',
            selectId: 'sort-simple-select',
            value: sortValue,
            onChange: (e: any) => setSortValue(e?.target?.value),
            menuItems: [
                { value: 'newest_oldest', label: 'Newest - Oldest' },
                { value: 'oldest_newest', label: 'Oldest - Newest' },
                { value: 'number_of_responses', label: 'No. of responses' },
                { value: 'deletion_requests', label: 'Deletion requests' },
                { value: 'latest_updated', label: 'Latest updated' },
                { value: 'alphabetical', label: 'Alphabetical' }
            ]
        },
        {
            id: 'filter-select-label',
            label: 'Show all',
            selectId: 'filter-simple-select',
            value: filterValue,
            onChange: (e: any) => setFilterValue(e?.target?.value),
            menuItems: [
                { value: 'show_all', label: 'Show all' },
                { value: 'googleform', label: 'Google Forms' },
                { value: 'typeform', label: 'Typeform' },
                { value: 'deletion_requests', label: 'Deletion requests' }
            ]
        }
    ];

    const dataTableFormColumns = [
        {
            name: t(formsConstant.formType),
            selector: (form: StandardFormDto) => <DataTableProviderFormCell form={form} workspace={workspace} />,
            grow: 2,
            style: {
                color: '#202124',
                fontSize: '16px',
                marginLeft: '-5px',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: t(formsConstant.responses),
            selector: (row: StandardFormDto) => (
                <ActiveLink className="hover:text-brand-500 hover:underline" href={`/${workspace.workspaceName}/dashboard/forms/${row.formId}/responses`}>
                    {row?.responses ?? 0}
                </ActiveLink>
            ),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '18px'
            }
        },
        {
            name: t(formsConstant.deletionRequests),
            selector: (row: StandardFormDto) => (
                <ActiveLink className="hover:text-brand-500 hover:underline paragraph" href={`/${workspace.workspaceName}/dashboard/forms/${row.formId}/deletion-requests`}>
                    {' '}
                    {row?.deletionRequests ?? 0}
                </ActiveLink>
            ),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '18px'
            }
        },
        {
            name: t(formsConstant.importedDate),
            selector: (row: StandardFormDto) => (!!row?.createdAt ? `${toMonthDateYearStr(parseDateStrToDate(utcToLocalDate(row.createdAt)))} ${toHourMinStr(parseDateStrToDate(utcToLocalDate(row.createdAt)))}` : ''),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },
        {
            cell: (form: StandardFormDto) => <FormOptionsDropdownMenu redirectToDashboard={false} form={form} hasCustomDomain={hasCustomDomain} workspace={workspace} />,
            allowOverflow: true,
            button: true,
            width: '60px',
            style: {
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        }
    ];
    // const handleSearch = async (event: any) => {
    //     const response: any = await searchWorkspaceForms({
    //         workspace_id: workspace.id,
    //         query: escapeRegExp(event.target.value)
    //     });
    //     if (event.target.value) {
    //         setForms(response?.data);
    //     } else {
    //         setForms(workspaceForms?.data?.items);
    //     }
    // };
    // const debouncedResults = useMemo(() => {
    //     return debounce(handleSearch, 500);
    // }, []);
    // useEffect(() => {
    //     debouncedResults.cancel();
    // }, []);

    return (
        <SidebarLayout>
            <div className="py-10 w-full h-full">
                <h1 className="sh1">{t(formsConstant.default)}</h1>
                <div className="flex flex-col mt-4 mb-6 gap-6 justify-center md:flex-row md:justify-between md:items-center">
                    {/* <StyledTextField>
                        <TextField
                            sx={{ height: '46px', padding: 0 }}
                            size="small"
                            name="search-input"
                            placeholder="Search"
                            onChange={debouncedResults}
                            className={'w-full'}
                            InputProps={{
                                sx: {
                                    padding: '16px'
                                },
                                endAdornment: (
                                    <InputAdornment sx={{ padding: 0 }} position="end">
                                        <SearchIcon />
                                    </InputAdornment>
                                )
                            }}
                        />
                    </StyledTextField> */}
                    <ImportFormsButton size="small" />
                    {/*<div className="grid grid-cols-2 items-center gap-2">*/}
                    {/*    {selectList.map((item) => (*/}
                    {/*        <FormControl key={item.id} variant="outlined" sx={{ height: '36px' }} hiddenLabel size="small">*/}
                    {/*            <InputLabel id={item.id}>{item.label}</InputLabel>*/}
                    {/*            <Select*/}
                    {/*                labelId={item.id}*/}
                    {/*                id={item.selectId}*/}
                    {/*                MenuProps={{*/}
                    {/*                    disableScrollLock: true*/}
                    {/*                }}*/}
                    {/*                sx={{ height: '36px' }}*/}
                    {/*                color="primary"*/}
                    {/*                IconComponent={ExpandMoreOutlined}*/}
                    {/*                value={item.value}*/}
                    {/*                label={item.label}*/}
                    {/*                onChange={item.onChange}*/}
                    {/*            >*/}
                    {/*                {item.menuItems.map((menuItem) => (*/}
                    {/*                    <MenuItem key={menuItem.value} value={menuItem.value}>*/}
                    {/*                        {menuItem.label}*/}
                    {/*                    </MenuItem>*/}
                    {/*                ))}*/}
                    {/*            </Select>*/}
                    {/*        </FormControl>*/}
                    {/*    ))}*/}
                    {/*</div>*/}
                </div>
                <Divider />

                {/* @ts-ignore */}
                <DataTable className="p-0 mt-2" columns={dataTableFormColumns} data={forms} customStyles={dataTableCustomStyles} highlightOnHover={false} pointerOnHover={false} />
            </div>
        </SidebarLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';

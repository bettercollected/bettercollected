import React, { useState } from 'react';

import { ExpandMoreOutlined } from '@mui/icons-material';
import { Divider, FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import DataTable from 'react-data-table-component';

import { dataTableCustomStyles } from '@app/components/form-datatable/datatable-styles';
import FormOptionsDropdownMenu from '@app/components/form-datatable/form-options-dropdown';
import DataTableProviderFormCell from '@app/components/form-datatable/provider-form-cell';
import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';

export default function FormPage({ workspace, hasCustomDomain }: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const [sortValue, setSortValue] = useState('newest_oldest');
    const [filterValue, setFilterValue] = useState('show_all');

    const workspaceQuery = {
        workspace_id: workspace.id
    };

    const workspaceForms = useGetWorkspaceFormsQuery<any>(workspaceQuery, { pollingInterval: 30000 });
    const forms = workspaceForms?.data?.items;

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
            name: 'Form type',
            selector: (form: StandardFormDto) => <DataTableProviderFormCell form={form} workspace={workspace} />,
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
            name: 'Responses',
            selector: (row: StandardFormDto) => row?.responses ?? 0,
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: 'Deletion requests',
            selector: (row: StandardFormDto) => row?.deletionRequests ?? 0,
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: 'Imported date',
            selector: (row: StandardFormDto) => 'hey' ?? row?.createdAt,
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
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

    return (
        <SidebarLayout>
            <div className="py-10 w-full h-full">
                <h1 className="sh1">Forms</h1>
                <div className="flex flex-col mt-4 mb-6 gap-6 justify-center md:flex-row md:justify-between md:items-center">
                    <ImportFormsButton size="small" />
                    <div className="grid grid-cols-2 items-center gap-2">
                        {selectList.map((item) => (
                            <FormControl key={item.id} variant="outlined" sx={{ height: '36px' }} hiddenLabel size="small">
                                <InputLabel id={item.id}>{item.label}</InputLabel>
                                <Select
                                    labelId={item.id}
                                    id={item.selectId}
                                    MenuProps={{
                                        disableScrollLock: true
                                    }}
                                    sx={{ height: '36px' }}
                                    color="primary"
                                    IconComponent={ExpandMoreOutlined}
                                    value={item.value}
                                    label={item.label}
                                    onChange={item.onChange}
                                >
                                    {item.menuItems.map((menuItem) => (
                                        <MenuItem key={menuItem.value} value={menuItem.value}>
                                            {menuItem.label}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        ))}
                    </div>
                </div>
                <Divider />

                {/* @ts-ignore */}
                <DataTable className="p-0 mt-2" columns={dataTableFormColumns} data={forms} customStyles={dataTableCustomStyles} highlightOnHover={false} pointerOnHover={false} />
            </div>
        </SidebarLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';

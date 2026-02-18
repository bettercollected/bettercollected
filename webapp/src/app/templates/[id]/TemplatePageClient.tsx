'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'react-toastify';
import { MenuItem } from '@mui/material';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import BetterCollectedForm from '@Components/Form/BetterCollectedForm';

import ActiveLink from '@app/Components/ui/links/active-link';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetStatusQuery } from '@app/store/auth/api';
import { useCreateFormFromTemplateMutation, useGetTemplateByIdQuery, useImportTemplateMutation } from '@app/store/template/api';
import { useGetAllMineWorkspacesQuery } from '@app/store/workspaces/api';
import { convertFormTemplateToStandardForm } from '@app/utils/convertDataType';
import environments from '@app/configs/environments';

export default function TemplatePageClient({ templateId }: { templateId: string }) {
    const { data } = useGetTemplateByIdQuery({
        template_id: templateId
    });

    const { data: auth, isError } = useGetStatusQuery(undefined, {
        refetchOnFocus: true
    });

    const router = useRouter();

    const [importTemplate] = useImportTemplateMutation();
    const [createFormFromTemplate] = useCreateFormFromTemplateMutation();

    const { data: myWorkspaces, refetch } = useGetAllMineWorkspacesQuery();

    useEffect(() => {
        refetch();
    }, [auth]);

    const handleImportTemplate = async (workspace: WorkspaceDto) => {
        const request = {
            workspace_id: workspace.id,
            template_id: templateId
        };
        try {
            const response: any = await importTemplate(request);
            if (response?.data) {
                toast('Imported Successfully', { type: 'success' });
                router.replace(`/${workspace.workspaceName}/templates/${response?.data?.id}`);
            } else {
                toast('Error Occurred', { type: 'error' });
            }
        } catch (err) {
            toast('Error Occurred', { type: 'error' });
        }
    };

    const handleUseTemplate = async (workspace: WorkspaceDto) => {
        const request = {
            workspace_id: workspace.id,
            template_id: templateId
        };
        try {
            const response: any = await createFormFromTemplate(request);
            if (response?.data) {
                toast('Created Form Successfully', { type: 'success' });
                const editFormUrl = `/${workspace.workspaceName}/dashboard/forms/${response?.data?.formId}/edit`;
                if (response?.data?.builderVersion === 'v2') {
                    window.location.href = environments.HTTP_SCHEME + environments.DASHBOARD_DOMAIN + editFormUrl;
                } else {
                    router.push(editFormUrl);
                }
            } else {
                toast('Error Occurred', { type: 'error' });
            }
        } catch (err) {
            toast('Error Occurred', { type: 'error' });
        }
    };

    return (
        <Layout showNavbar className="bg-white !px-0">
            <div className={'flex justify-end px-5 py-3'}>
                <div className={'flex flex-row gap-4'}>
                    {!isError && auth ? (
                        <>
                            <ButtonActionWrapper handleAction={handleImportTemplate} workspaces={myWorkspaces}>
                                <AppButton disabled={!data} variant={ButtonVariant.Secondary}>
                                    Import Template
                                </AppButton>
                            </ButtonActionWrapper>
                            <ButtonActionWrapper handleAction={handleUseTemplate} workspaces={myWorkspaces}>
                                <AppButton disabled={!data}>Use Template</AppButton>
                            </ButtonActionWrapper>
                        </>
                    ) : (
                        <ActiveLink href="/login" target="_blank" referrerPolicy="no-referrer">
                            <AppButton>Import Template</AppButton>
                        </ActiveLink>
                    )}
                </div>
            </div>
            {data && <BetterCollectedForm isDisabled form={convertFormTemplateToStandardForm(data)} />}
        </Layout>
    );
}

const ButtonActionWrapper = ({ children, handleAction, workspaces }: any) => {
    const hasSingleWorkspace = workspaces && Array.isArray(workspaces) && workspaces.length === 1;
    const workspace = hasSingleWorkspace ? workspaces[0] : undefined;
    return (
        <div>
            {hasSingleWorkspace && (
                <div
                    onClick={() => {
                        handleAction(workspace);
                    }}
                >
                    {children}
                </div>
            )}
            {!hasSingleWorkspace && (
                <MenuDropdown id="workspaceSelector" className="hover:bg-transparent" menuTitle="Select a workspace" showExpandMore={false} menuContent={<div className="pointer-events-none ">{children}</div>}>
                    <div className="text-black-700 px-4 py-2 text-sm font-bold">Select a workspace</div>
                    <div>
                        {workspaces?.map((workspace: WorkspaceDto) => (
                            <MenuItem
                                key={workspace.id}
                                onClick={() => {
                                    handleAction(workspace);
                                }}
                            >
                                {workspace.title}
                            </MenuItem>
                        ))}
                    </div>
                </MenuDropdown>
            )}
        </div>
    );
}

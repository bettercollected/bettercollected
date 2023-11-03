import React, { useEffect } from 'react';

import { serverSideTranslations } from 'next-i18next/serverSideTranslations';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import BetterCollectedForm from '@Components/Form/BetterCollectedForm';
import { MenuItem } from '@mui/material';
import { toast } from 'react-toastify';

import ActiveLink from '@app/components/ui/links/active-link';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetStatusQuery } from '@app/store/auth/api';
import { useCreateFormFromTemplateMutation, useGetTemplateByIdQuery, useImportTemplateMutation } from '@app/store/template/api';
import { useGetAllMineWorkspacesQuery } from '@app/store/workspaces/api';
import { convertFormTemplateToStandardForm } from '@app/utils/convertDataType';
import { checkHasAdminDomain, getRequestHost } from '@app/utils/serverSidePropsUtils';

export default function TemplatePage(props: any) {
    const { templateId } = props;
    const { data } = useGetTemplateByIdQuery({
        template_id: templateId
    });

    const { data: auth, isError } = useGetStatusQuery(undefined, {
        refetchOnFocus: true
    });

    const router = useRouter();

    const [importTemplate] = useImportTemplateMutation();
    const [createFormFromTemplate] = useCreateFormFromTemplateMutation();

    const { data: myWorkspaces, isLoading: myWorkspaceLoading, refetch } = useGetAllMineWorkspacesQuery();
    console.log(auth);

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
                await router.replace(`/${workspace.workspaceName}/templates/${response?.data?.id}`);
            } else {
                toast('Error Occurred').toString(), { type: 'error' };
            }
        } catch (err) {
            toast('Error Occurred').toString(), { type: 'error' };
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
                await router.replace(`/${workspace.workspaceName}/dashboard/forms/${response?.data?.formId}/edit`);
            } else {
                toast('Error Occurred').toString(), { type: 'error' };
            }
        } catch (err) {
            toast('Error Occurred').toString(), { type: 'error' };
        }
    };

    return (
        <Layout showNavbar className="bg-white !px-0">
            <div className={'py-3 px-5 flex justify-end'}>
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
                            <AppButton variant={ButtonVariant.Ghost}>Login to Use or Import template</AppButton>
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
                    <div className="font-bold px-4 py-2 text-sm text-black-700">Select a workspace</div>
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
};

export async function getServerSideProps(_context: any) {
    const hasAdminDomain = checkHasAdminDomain(getRequestHost(_context));

    if (!hasAdminDomain) {
        return {
            redirect: {
                path: '/',
                permanent: false
            }
        };
    }
    const { id } = _context.params;
    return {
        props: {
            ...(await serverSideTranslations(_context.locale, ['common', 'builder'], null, ['en', 'nl'])),
            templateId: id
        }
    };
}

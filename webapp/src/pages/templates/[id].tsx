import React from 'react';

import { serverSideTranslations } from 'next-i18next/serverSideTranslations';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import BetterCollectedForm from '@Components/Form/BetterCollectedForm';
import { MenuItem } from '@mui/material';

import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetTemplateByIdQuery } from '@app/store/template/api';
import { useGetAllMineWorkspacesQuery } from '@app/store/workspaces/api';
import { convertFormTemplateToStandardForm } from '@app/utils/convertDataType';
import { checkHasAdminDomain, getRequestHost } from '@app/utils/serverSidePropsUtils';

export default function TemplatePage(props: any) {
    const { templateId } = props;
    const { data } = useGetTemplateByIdQuery({
        template_id: templateId
    });

    const { data: myWorkspaces, isLoading: myWorkspaceLoading } = useGetAllMineWorkspacesQuery();

    const handleImportTemplate = (workspace: WorkspaceDto) => {};

    const handleUseTemplate = (workspace: WorkspaceDto) => {};

    return (
        <Layout showNavbar className="bg-white !px-0">
            <div className={'py-3 px-5 flex justify-end'}>
                <div className={'flex flex-row gap-4'}>
                    <ButtonActionWrapper handleAction={handleImportTemplate} workspaces={myWorkspaces}>
                        <AppButton disabled={!data} variant={ButtonVariant.Secondary}>
                            Import Template
                        </AppButton>
                    </ButtonActionWrapper>
                    <ButtonActionWrapper handleAction={handleUseTemplate} workspaces={myWorkspaces}>
                        <AppButton disabled={!data}>Use Template</AppButton>
                    </ButtonActionWrapper>
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

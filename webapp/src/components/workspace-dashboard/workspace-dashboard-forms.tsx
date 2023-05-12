import React from 'react';

import { useTranslation } from 'next-i18next';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import { EmptyImportFormIcon } from '@app/components/icons/empty-import-form-icon';
import ActiveLink from '@app/components/ui/links/active-link';
import WorkspaceFormCard from '@app/components/workspace-dashboard/workspace-form-card';
import { formsConstant } from '@app/constants/locales';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface IWorkspaceDashboardFormsProps {
    workspaceForms: any;
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
}

export default function WorkspaceDashboardForms({ workspaceForms, workspace, hasCustomDomain }: IWorkspaceDashboardFormsProps) {
    const forms = workspaceForms?.data?.items;
    const { t } = useTranslation();

    return (
        <div className="mb-10 w-full h-fit mt-5">
            {forms?.length === 0 ? (
                <div className="w-full h-full flex flex-col items-center justify-center bg-white rounded-[4px] py-[84px]">
                    <EmptyImportFormIcon className="mb-8" />
                    <p className="sh1 mb-4 !leading-none">{t(formsConstant.empty.title)}</p>
                    <p className="body4 mb-8 !leading-none">{t(formsConstant.empty.description)}</p>
                    <ImportFormsButton size="medium" />
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-6">
                    {forms?.length !== 0 &&
                        forms?.map((form: StandardFormDto) => (
                            <ActiveLink key={form.formId} href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}`}>
                                <WorkspaceFormCard form={form} workspace={workspace} hasCustomDomain={hasCustomDomain} />
                            </ActiveLink>
                        ))}
                </div>
            )}
        </div>
    );
}

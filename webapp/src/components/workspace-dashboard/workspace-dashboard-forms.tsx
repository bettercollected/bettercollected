import React from 'react';

import { useTranslation } from 'next-i18next';

import CreateFormButton from '@Components/Common/CreateFormButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import BeaconComponent from '@Components/Joyride/JoyrideBeacon';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import WorkspaceFormCard from '@app/components/workspace-dashboard/workspace-form-card';
import { localesCommon } from '@app/constants/locales/common';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { JOYRIDE_CLASS } from '@app/store/tours/types';

interface IWorkspaceDashboardFormsProps {
    workspaceForms: any;
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
}

export default function WorkspaceDashboardForms({ workspaceForms, workspace, hasCustomDomain }: IWorkspaceDashboardFormsProps) {
    const forms = workspaceForms?.data?.items;
    const { t } = useTranslation();

    const ref = React.useRef<HTMLDivElement>(null);

    if (workspaceForms.isLoading) {
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    }

    return (
        <div className="w-full mb-10 flex flex-col gap-5 h-fit">
            <div className="min-h-9 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
                <p className="sh1">{t(localesCommon.forms)}</p>
                <div className="flex gap-3">
                    <ImportFormsButton className={JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_IMPORT_FORM_BUTTON} />
                    <CreateFormButton />
                </div>
            </div>
            {forms?.length === 0 ? (
                <div className="w-full h-full flex flex-col items-center justify-center rounded-lg py-[84px]">
                    <p className="h3-new text-black-800 font-semibold">You haven&apos;t created or imported any forms.</p>
                    <p className="p1-new text-black-700 mb-6 mt-2">Create your first privacy friendly form.</p>
                    <div ref={ref} className="relative">
                        <CreateFormButton variant={ButtonVariant.Tertiary} />
                        <div className="absolute -bottom-1 -right-1">
                            <BeaconComponent />
                        </div>
                    </div>
                </div>
            ) : (
                <div className="flex flex-col gap-6">
                    {forms?.length !== 0 &&
                        forms?.map((form: StandardFormDto, index: number) => (
                            <ActiveLink key={form.formId} href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}`}>
                                <WorkspaceFormCard index={index} form={form} workspace={workspace} hasCustomDomain={hasCustomDomain} />
                            </ActiveLink>
                        ))}
                </div>
            )}
        </div>
    );
}

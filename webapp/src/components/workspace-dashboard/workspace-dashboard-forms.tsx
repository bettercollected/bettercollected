import React from 'react';

import { useTranslation } from 'next-i18next';

import Joyride from '@Components/Joyride';
import { JoyrideStepContent, JoyrideStepTitle } from '@Components/Joyride/JoyrideStepTitleAndContent';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import { EmptyImportFormIcon } from '@app/components/icons/empty-import-form-icon';
import { useModal } from '@app/components/modal-views/context';
import ActiveLink from '@app/components/ui/links/active-link';
import WorkspaceFormCard from '@app/components/workspace-dashboard/workspace-form-card';
import environments from '@app/configs/environments';
import { formConstant } from '@app/constants/locales/form';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { JOYRIDE_ID } from '@app/store/tours/types';

interface IWorkspaceDashboardFormsProps {
    workspaceForms: any;
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
}

export default function WorkspaceDashboardForms({ workspaceForms, workspace, hasCustomDomain }: IWorkspaceDashboardFormsProps) {
    const { isOpen, view } = useModal();

    const forms = workspaceForms?.data?.items;
    const { t } = useTranslation();

    const ref = React.useRef<HTMLDivElement>(null);
    const [firstStepClicked, setFirstStepClicked] = React.useState(false);

    const handleOnClick = () => {
        setFirstStepClicked(true);
    };

    return (
        <div className="mb-10 w-full h-fit mt-5">
            {forms?.length === 0 ? (
                <div className="w-full h-full flex flex-col items-center justify-center bg-white rounded-[4px] py-[84px]">
                    {ref.current && environments.ENABLE_JOYRIDE_TOURS && (
                        <Joyride
                            id={JOYRIDE_ID.WORKSPACE_ADMIN_FORM_IMPORT_BUTTON}
                            placement="top"
                            continuous={false}
                            showCloseButton={false}
                            firstStepClicked={isOpen && view === 'IMPORT_PROVIDER_FORMS_VIEW' && firstStepClicked}
                            steps={[
                                {
                                    title: <JoyrideStepTitle text="You are one step closer to importing the forms" />,
                                    content: <JoyrideStepContent>Import your forms from other providers into Better Collected. Click &quot;Import Forms&quot; button below to import your forms.</JoyrideStepContent>,
                                    target: ref.current,
                                    placementBeacon: 'bottom-start',
                                    hideFooter: true
                                }
                            ]}
                        />
                    )}
                    <EmptyImportFormIcon className="mb-6 h-[71px] w-[71px] " />
                    <p className="sh1 mb-[15px] !leading-none">{t(formConstant.empty.title)}</p>
                    <p className="body4 mb-6 !leading-none">{t(formConstant.empty.description)}</p>
                    <div ref={ref} onClick={handleOnClick} className="animate-pulse hover:animate-none">
                        <ImportFormsButton size="medium" />
                    </div>
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-6">
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

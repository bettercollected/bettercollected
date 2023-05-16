import React from 'react';

import Joyride from '@Components/Joyride';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import { EmptyImportFormIcon } from '@app/components/icons/empty-import-form-icon';
import { useModal } from '@app/components/modal-views/context';
import ActiveLink from '@app/components/ui/links/active-link';
import WorkspaceFormCard from '@app/components/workspace-dashboard/workspace-form-card';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface IWorkspaceDashboardFormsProps {
    workspaceForms: any;
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
}

export default function WorkspaceDashboardForms({ workspaceForms, workspace, hasCustomDomain }: IWorkspaceDashboardFormsProps) {
    const { isOpen, view } = useModal();

    const forms = workspaceForms?.data?.items;

    const ref = React.useRef<HTMLDivElement>(null);
    const [firstStepClicked, setFirstStepClicked] = React.useState(false);

    const handleOnClick = () => {
        setFirstStepClicked(true);
    };

    return (
        <div className="mb-10 w-full h-fit mt-5">
            {forms?.length === 0 ? (
                <div className="w-full h-full flex flex-col items-center justify-center bg-white rounded-[4px] py-[84px]">
                    {ref.current && (
                        <Joyride
                            id="workspace-admin-form-import-button"
                            placement="top"
                            continuous={false}
                            showCloseButton={false}
                            firstStepClicked={isOpen && view === 'IMPORT_PROVIDER_FORMS_VIEW' && firstStepClicked}
                            steps={[
                                {
                                    title: <span className="sh3">You are one step closer to importing the forms</span>,
                                    content: <p className="body4">Import your forms from other providers into Better Collected. Click &quot;Import Forms&quot; button below to import your forms.</p>,
                                    target: ref.current,
                                    placementBeacon: 'bottom-start',
                                    disableBeacon: true,
                                    disableOverlayClose: true,
                                    hideCloseButton: true,
                                    disableCloseOnEsc: true,
                                    showSkipButton: false,
                                    hideBackButton: true,
                                    hideFooter: true
                                }
                            ]}
                        />
                    )}
                    <EmptyImportFormIcon className="mb-8" />
                    <p className="sh1 mb-4 !leading-none">Import your first form</p>
                    <p className="body4 mb-8 !leading-none">Import your Google Forms or Typeforms</p>
                    <div ref={ref} onClick={handleOnClick}>
                        <ImportFormsButton size="medium" />
                    </div>
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

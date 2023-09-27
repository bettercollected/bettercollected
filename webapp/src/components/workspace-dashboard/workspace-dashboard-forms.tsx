import React from 'react';

import {useTranslation} from 'next-i18next';
import BeaconComponent from '@Components/Joyride/JoyrideBeacon';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import {EmptyImportFormIcon} from '@app/components/icons/empty-import-form-icon';
import {useModal} from '@app/components/modal-views/context';
import ActiveLink from '@app/components/ui/links/active-link';
import WorkspaceFormCard from '@app/components/workspace-dashboard/workspace-form-card';
import {formConstant} from '@app/constants/locales/form';
import {StandardFormDto} from '@app/models/dtos/form';
import {WorkspaceDto} from '@app/models/dtos/workspaceDto';
import {ButtonSize} from "@Components/Common/Input/Button/AppButtonProps";

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
        <div className="my-10 w-full h-fit">
            {forms?.length === 0 ? (
                <div className="w-full h-full flex flex-col items-center justify-center rounded-lg py-[84px]">
                    <EmptyImportFormIcon className="mb-6" />
                    <p className="sh1 mb-[15px] !leading-none">{t(formConstant.empty.title)}</p>
                    <p className="body4 mb-6 !leading-none">{t(formConstant.empty.description)}</p>
                    <div ref={ref} onClick={handleOnClick} className="relative">
                        <ImportFormsButton size={ButtonSize.Medium} />
                        <div className="absolute bottom-0 right-0">
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

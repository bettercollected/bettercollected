import React from 'react';

import CreateFormButton from '@Components/Common/CreateFormButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import BeaconComponent from '@Components/Joyride/JoyrideBeacon';

import ActiveLink from '@app/components/ui/links/active-link';
import WorkspaceFormCard from '@app/components/workspace-dashboard/workspace-form-card';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface IWorkspaceDashboardFormsCardProps {
    workspaceForms: any;
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
    showPinned?: boolean;
    showEmpty?: boolean;
}

export default function WorkspaceDashboardFormsCard({ workspaceForms, workspace, hasCustomDomain, showPinned = false, showEmpty = false }: IWorkspaceDashboardFormsCardProps) {
    const forms = workspaceForms;
    const ref = React.useRef<HTMLDivElement>(null);

    // @ts-ignore
    return (
        <div className="w-full mb-4 flex flex-col gap-5 h-fit">
            {forms?.length === 0 ? (
                showEmpty ? (
                    <div className=" h4-new flex h-full justify-center text-black-800 items-center w-full min-h-[150px]">No forms found</div>
                ) : (
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
                )
            ) : (
                <div className="flex flex-col gap-6">
                    {forms?.length !== 0 &&
                        forms?.map((form: StandardFormDto, index: number) => (
                            <ActiveLink key={form.formId} href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}`}>
                                <WorkspaceFormCard index={index} showPinned={showPinned} form={form} workspace={workspace} hasCustomDomain={hasCustomDomain} />
                            </ActiveLink>
                        ))}
                </div>
            )}
        </div>
    );
}

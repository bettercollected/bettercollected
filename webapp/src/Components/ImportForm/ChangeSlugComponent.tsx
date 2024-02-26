import React from 'react';

import { useRouter } from 'next/router';

import CheckedCircle from '@Components/Common/Icons/Common/CheckedCircle';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';


export default function ChangeSlugComponent() {
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    return (
        <div className="md:w-[500px] max-w-full px-5">
            <div className="flex gap-4 items-center justify-center mb-[72px]">
                <CheckedCircle />
                <span className="h3-new text-black-900">Form Imported Successfully!</span>
            </div>
            <div className="h4-new">Form Link</div>
            <FormSettingsTab view="LINKS" />
            <div className="mt-[72px] flex flex-col">
                <div className="text-black-700 mb-4 p2-new">You can always customize your form link later</div>
                <AppButton
                    variant={ButtonVariant.Primary}
                    size={ButtonSize.Medium}
                    onClick={() => {
                        router.push(`/${workspace.workspaceName}/dashboard`);
                    }}
                >
                    Done, Go to Dashboard
                </AppButton>
            </div>
        </div>
    );
}
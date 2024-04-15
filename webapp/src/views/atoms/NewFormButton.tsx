import AppButton from '@Components/Common/Input/Button/AppButton';
import environments from '@app/configs/environments';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useRouter } from 'next/navigation';
import React from 'react';

export default function NewFormButton() {
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    return (
        <AppButton
            onClick={() => {
                router.push(`${environments.HTTP_SCHEME}${environments.NEXT_PUBLIC_DASHBOARD_DOMAIN}/${workspace?.workspaceName}/dashboard/form/create`);
            }}
        >
            New Form
        </AppButton>
    );
}

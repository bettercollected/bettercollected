import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/navigation';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';

import environments from '@app/configs/environments';
import { builderConstants } from '@app/constants/locales/form-builder';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function CreateFormButton({ variant }: { variant?: ButtonVariant }) {
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    const { t: builderTranslation } = useTranslation('builder');

    const onClickButton = async () => {
        router.push(`${environments.HTTP_SCHEME}${environments.DASHBOARD_DOMAIN}/${workspace?.workspaceName}/dashboard/form/create`);
    };

    return (
        <>
            {environments.ENABLE_FORM_BUILDER && (
                <AppButton className="min-w-[160px]" variant={variant} onClick={onClickButton}>
                    {builderTranslation(builderConstants.createForm)}
                </AppButton>
            )}
        </>
    );
}

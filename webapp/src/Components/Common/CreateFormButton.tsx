import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/navigation';

import { Button } from '@app/shadcn/components/ui/button';
import environments from '@app/configs/environments';
import { builderConstants } from '@app/constants/locales/form-builder';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function CreateFormButton({ variant }: { variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link" | "primary" | "danger" }) {
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    const { t: builderTranslation } = useTranslation('builder');

    const onClickButton = async () => {
        router.push(`${environments.HTTP_SCHEME}${environments.DASHBOARD_DOMAIN}/${workspace?.workspaceName}/dashboard/form/create`);
    };

    return (
        <>
            {environments.ENABLE_FORM_BUILDER && (
                <Button className="min-w-[160px]" variant={variant as any} onClick={onClickButton}>
                    {builderTranslation(builderConstants.createForm)}
                </Button>
            )}
        </>
    );
}

import React, { ChangeEvent, FormEvent, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { handle } from 'mdast-util-to-markdown/lib/handle';

import BetterInput from '@app/components/Common/input';
import { useModal } from '@app/components/modal-views/context';
import SettingsCard from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import { advanceSetting, buttons, localesDefault } from '@app/constants/locales';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';

export default function UpdateCustomDomain() {
    const { t } = useTranslation();
    const workspace = useAppSelector((state) => state.workspace);
    const { openModal } = useModal();
    const router = useRouter();
    const isProPlan = useAppSelector(selectIsProPlan);

    const handleClick = () => {
        if (isProPlan) {
            openModal('UPDATE_WORKSPACE_DOMAIN');
        } else {
            router.push(`/${workspace.workspaceName}/upgrade`);
        }
    };

    return (
        <SettingsCard>
            <div className="body1">{t(localesDefault.customDomain)}</div>
            <div className="flex w-full justify-between">
                <div className="w-full text-sm text-gray-600">
                    {workspace.customDomain ? (
                        <>
                            {t(advanceSetting.customDomainSetDescription)}
                            <span className="font-bold"> {workspace.customDomain}.</span>
                        </>
                    ) : (
                        t(advanceSetting.customDomainNotSetDescription)
                    )}
                </div>
                <div>
                    <Button onClick={handleClick}>{t(buttons.update)}</Button>
                </div>
            </div>
        </SettingsCard>
    );
}

import React from 'react';

import { useTranslation } from 'next-i18next';

import AppButton from '@Components/Common/Input/Button/AppButton';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import SettingsCard from '@app/components/settings/card';
import { advanceSetting } from '@app/constants/locales/advance-setting';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { upgradeConst } from '@app/constants/locales/upgrade';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

export default function UpdateCustomDomain() {
    const { t } = useTranslation();
    const workspace = useAppSelector((state) => state.workspace);
    const { openModal } = useModal();
    const isProPlan = useAppSelector(selectIsProPlan);
    const upgradeModal = useFullScreenModal();

    const handleClick = () => {
        if (isProPlan) {
            openModal('UPDATE_WORKSPACE_DOMAIN');
        } else {
            upgradeModal.openModal('UPGRADE_TO_PRO', { featureText: t(upgradeConst.features.customDomain.slogan) });
        }
    };

    return (
        <SettingsCard>
            <div className="body1">{t(localesCommon.customDomain)}</div>
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
                    <AppButton onClick={handleClick}>{t(buttonConstant.update)}</AppButton>
                </div>
            </div>
        </SettingsCard>
    );
}

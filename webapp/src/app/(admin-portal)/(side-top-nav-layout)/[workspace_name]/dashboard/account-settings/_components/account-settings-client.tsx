"use client";


import AIMemorySection from '@app/components/account-settings/ai-memory-section';
import SecuritySection from '@app/components/account-settings/security-section';
import SessionsSection from '@app/components/account-settings/sessions-section';
import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import SettingCard from '@app/components/cards/setting-card';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { profileMenu } from '@app/constants/locales/profile-menu';
import { UserStatus } from '@app/models/dtos/user-status';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { getFullNameFromUser } from '@app/utils/user-utils';
import { useBottomSheetModal } from '@Components/modals/contexts/bottom-sheet-modal-context';
import { PageSurface } from '@app/components/ui/page-surface';

export default function AccountSettingsClient() {
    const { t } = useTranslation();
    const authStatus: UserStatus = useAppSelector(selectAuth);

    const { openBottomSheetModal } = useBottomSheetModal();

    const hasName = !!(authStatus.firstName || authStatus.lastName);
    const displayName = getFullNameFromUser(authStatus);

    return (
        <div className="flex w-full max-w-[760px] flex-col gap-6">
            <PageSurface>
            <h4 className="h4">{t(profileMenu.accountSettings)}</h4>
            <div className="flex gap-4">
                <AuthAccountProfileImage size={80} image={authStatus.profileImage} name={displayName} />
                <div className="flex flex-col gap-2 justify-center">
                    <p className="h4 leading-none!">{displayName}</p>
                    {hasName && <p className="body4 text-black-700 leading-none!">{authStatus.email}</p>}
                </div>
                </div>
            </PageSurface>
            <div className="flex flex-col gap-6">
                <SettingCard title={t(localesCommon.privacyPolicy.title)} description={t(localesCommon.privacyPolicy.description)} link="https://bettercollected.com/privacy-policy" />
                <SettingCard title={t(localesCommon.termsOfServices.title)} description={t(localesCommon.termsOfServices.description)} link="https://bettercollected.com/terms-of-service" />
                <AIMemorySection />
                <SecuritySection />
                <SessionsSection />
                {/* the same danger card as a form's Settings (components/form/settings.tsx): heading and sentence on the left, the button on the right */}
                <div className="flex flex-col items-start justify-between gap-4 rounded-lg border border-[#E5B9B9] bg-surface p-4 sm:flex-row sm:gap-6 sm:p-6">
                    <div className="flex max-w-[520px] flex-col gap-1">
                        <div className="text-[15px] font-semibold text-black-900">{t('DELETE_ACCOUNT.TITLE')}</div>
                        <div className="text-sm leading-relaxed text-black-700">{t('DELETE_ACCOUNT.DESCRIPTION')}</div>
                    </div>
                    <Button
                        variant="danger"
                        onClick={() => {
                            openBottomSheetModal('DELETE_ACCOUNT');
                        }}
                    >
                        {t(buttonConstant.deleteAccount)}
                    </Button>
                </div>
            </div>
        </div>
    );
}

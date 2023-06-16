import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { Button } from '@mui/material';
import { toast } from 'react-toastify';
import { Toast } from 'react-toastify/dist/components';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import SettingCard from '@app/components/cards/setting-card';
import { useModal } from '@app/components/modal-views/context';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { profileMenu } from '@app/constants/locales/profile-menu';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { UserStatus } from '@app/models/dtos/UserStatus';
import { useDeleteAccountMutation, useLazyGetStatusQuery } from '@app/store/auth/api';
import { initialAuthState, selectAuth, setAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { getFullNameFromUser } from '@app/utils/userUtils';

export default function AccountSettings(props: any) {
    const { t } = useTranslation();
    const authStatus: UserStatus = useAppSelector(selectAuth);
    const { openModal, closeModal } = useModal();
    const [deleteAccount] = useDeleteAccountMutation();
    const router = useRouter();
    const locale = router?.locale === 'en' ? '' : `${router.locale}/`;
    const handleDeleteAccount = async () => {
        try {
            await deleteAccount().unwrap();
            closeModal();
            router.push(`/${locale}login`);
            toast(t(toastMessage.accountDeletion.success).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
        } catch (e) {
            toast(t(toastMessage.accountDeletion.failed).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    return (
        <DashboardLayout>
            <div className="my-4">
                <h4 className="h4">{t(profileMenu.accountSettings)}</h4>
                <div className="mt-[30px] flex gap-4 mb-10">
                    <AuthAccountProfileImage size={80} image={authStatus.profileImage} name={authStatus.firstName ?? 'Anonymous'} />
                    <div className="flex flex-col gap-2 justify-center">
                        <p className="h4 !leading-none">{getFullNameFromUser(authStatus)}</p>
                        <p className="body4 text-black-700 !leading-none">{authStatus.email}</p>
                    </div>
                </div>
                <div className="flex flex-col gap-6">
                    <SettingCard title={t(localesCommon.privacyPolicy.title)} description={t(localesCommon.privacyPolicy.description)} link="https://bettercollected.com/privacy-policy" />
                    <SettingCard title={t(localesCommon.termsOfServices.title)} description={t(localesCommon.termsOfServices.description)} link="https://bettercollected.com/terms-of-service" />
                    <div className="my-6">
                        <Button
                            style={{ textTransform: 'none' }}
                            className="bg-red-100 px-4 !leading-none py-3 body6 rounded hover:bg-red-200 hover:drop-shadow-sm  !text-red-500"
                            size="medium"
                            onClick={() => {
                                openModal('USER_DELETION', { handleDelete: () => handleDeleteAccount() });
                            }}
                        >
                            {t(buttonConstant.deleteAccount)}
                        </Button>
                    </div>
                </div>
            </div>
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';

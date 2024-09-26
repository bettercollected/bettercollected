import React from 'react';
import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import AuthNavbar from '@app/Components/auth/navbar';
import { useRouter } from 'next/router';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

const ExpiredInvitation: React.FC = () => {
    const { t } = useTranslation();
    const router = useRouter();
    const { workspaceName } = useAppSelector(selectWorkspace);

    const handleReturn = () => {
        router.push('/');
    };

    return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-gray-100">
            <NextSeo title={`${t('Invitation Expired')} | ${workspaceName}`} noindex={true} nofollow={true} />
            <AuthNavbar showHamburgerIcon={false} showPlans={false} />
            <div className="mx-6 flex w-full flex-col items-center rounded-lg border bg-white p-10 shadow-lg md:max-w-[520px]">
                <div className="text-center text-xl font-semibold text-red-600">{t('Invitation Expired')}</div>
                <p className="mt-4 text-center text-gray-800">{t('The invitation you are trying to access has expired.')}</p>
                <button onClick={handleReturn} className="mt-6 rounded-lg bg-blue-500 px-6 py-2 text-white hover:bg-blue-700">
                    {t('Return to Workspace')}
                </button>
            </div>
        </div>
    );
};

export default ExpiredInvitation;

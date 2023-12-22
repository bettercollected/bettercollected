import React, { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { isLocalURL } from 'next/dist/shared/lib/router/router';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import ImportForm from '@Components/ImportForm/ImportForm';

import { ChevronForward } from '@app/components/icons/chevron-forward';
import { useModal } from '@app/components/modal-views/context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Loader from '@app/components/ui/loader';
import Layout from '@app/layouts/_layout';
import { useAppSelector } from '@app/store/hooks';
import { useVerifyFormTokenQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ImportFormPage() {
    const { t } = useTranslation();
    const { title } = useAppSelector(selectWorkspace);
    const router = useRouter();
    const { openModal } = useModal();

    const { data, isLoading, error: verificationError } = useVerifyFormTokenQuery({ provider: 'google' });

    const workspace = useAppSelector(selectWorkspace);

    useEffect(() => {
        if (verificationError || data?.status_code === 400) {
            openModal('OAUTH_VERIFICATION_MODAL', { provider: 'google', nonClosable: true });
        }

        if (data?.status_code === 200) {
            router.push(`/${workspace?.workspaceName}/dashboard/forms/import`);
        }
    }, [verificationError, data]);
    const handleClickBack = () => {
        router.back();
    };

    return (
        <Layout showNavbar={true} className="!p-0 bg-white flex flex-col min-h-screen">
            <NextSeo title={'Import-form | ' + title} noindex={true} nofollow={true} />
            <div className={'flex flex-col gap-11'}>
                <div className="flex w-fit items-center gap-1 px-2 md:px-5 pt-2 cursor-pointer" onClick={handleClickBack}>
                    <ChevronForward className=" rotate-180 h-6 w-6 p-[2px] " />
                    <p className={'text-sm text-black-700 font-normal'}>{t('BUTTON.BACK')}</p>
                </div>
                <div className={'flex flex-col items-center'}>
                    {data && <ImportForm />}
                    {isLoading && (
                        <div className="min-h-[400px]">
                            <Loader variant="blink" />
                        </div>
                    )}
                </div>
            </div>
        </Layout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';

import React, { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { useRouter } from 'next/router';

import ImportForm from '@Components/ImportForm/ImportForm';

import { ChevronForward } from '@app/components/icons/chevron-forward';
import { useModal } from '@app/components/modal-views/context';
import Loader from '@app/components/ui/loader';
import Layout from '@app/layouts/_layout';
import { resetSingleForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useVerifyFormTokenMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';


export default function ImportFormPage() {
    const { t } = useTranslation();
    const { title } = useAppSelector(selectWorkspace);
    const router = useRouter();
    const { openModal } = useModal();
    const dispatch = useAppDispatch();
    const [trigger, { data, isLoading, error: verificationError }] = useVerifyFormTokenMutation();

    const workspace = useAppSelector(selectWorkspace);

    useEffect(() => {
        trigger({ provider: 'google' });
        dispatch(resetSingleForm());
        return () => {
            dispatch(resetSingleForm());
        };
    }, []);

    useEffect(() => {
        if (verificationError || data?.status_code === 400) {
            openModal('OAUTH_ERROR_VIEW', { provider: 'google', nonClosable: true });
        }
    }, [verificationError, data]);
    const handleClickBack = () => {
        router.push(`/${workspace?.workspaceName}/dashboard`);
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
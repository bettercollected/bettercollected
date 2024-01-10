import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import ImportForm from '@Components/ImportForm/ImportForm';
import useDrivePicker from '@fyelci/react-google-drive-picker';

import { ChevronForward } from '@app/components/icons/chevron-forward';
import { useModal } from '@app/components/modal-views/context';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import Layout from '@app/layouts/_layout';
import { resetSingleForm, selectForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useVerifyFormTokenMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ImportFormPage() {
    const { t } = useTranslation();
    const { title } = useAppSelector(selectWorkspace);
    const router = useRouter();
    const { closeModal } = useModal();
    const dispatch = useAppDispatch();

    const form = useAppSelector(selectForm);

    const [verifyToken, { isLoading, data, error: verificationError }] = useVerifyFormTokenMutation();

    const workspace = useAppSelector(selectWorkspace);

    const [openPicker] = useDrivePicker();

    const [formId, setFormId] = useState('');

    useEffect(() => {
        dispatch(resetSingleForm());
        verifyToken({ provider: 'google' });
        return () => {
            dispatch(resetSingleForm());
        };
    }, []);

    const openGoogleFilePicker = () => {
        openPicker({
            clientId: environments.GOOGLE_CLIENT_ID,
            developerKey: environments.GOOGLE_PICKER_API_KEY,
            viewId: 'FORMS',
            token: data,
            customScopes: ['https://www.googleapis.com/auth/drive.file'],
            callbackFunction: (data) => {
                if (data.action === 'picked' && data.docs && Array.isArray(data.docs) && data.docs.length > 0) {
                    const formId = data.docs[0].id;
                    setFormId(formId);
                } else if (data.action === 'cancel') {
                    closeModal();
                }
            }
        });
    };

    useEffect(() => {
        if (data) {
            openGoogleFilePicker();
        }
    }, [data]);

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
                    {data && (
                        <>
                            <ImportForm formId={formId} />
                            {!form?.formId && (
                                <AppButton
                                    className="mt-20"
                                    variant={ButtonVariant.Ghost}
                                    size={ButtonSize.Medium}
                                    onClick={() => {
                                        openGoogleFilePicker();
                                    }}
                                >
                                    Open Google File Picker
                                </AppButton>
                            )}
                        </>
                    )}
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

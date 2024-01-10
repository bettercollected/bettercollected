import React from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { useRouter } from 'next/router';

import LoadingIcon from '@Components/Common/Icons/Common/Loading';
import SettingsIcon from '@Components/Common/Icons/Common/Settings';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import BetterCollectedForm from '@Components/Form/BetterCollectedForm';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import { toast } from 'react-toastify';

import { ChevronForward } from '@app/components/icons/chevron-forward';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import Layout from '@app/layouts/_layout';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { useCreateFormFromTemplateMutation, useGetTemplateByIdQuery, useImportTemplateMutation } from '@app/store/template/api';
import { convertFormTemplateToStandardForm } from '@app/utils/convertDataType';

const SingleTemplate = (props: any) => {
    const { workspace, notFound, templateId } = props;
    const router = useRouter();
    const { openBottomSheetModal } = useBottomSheetModal();
    const { t } = useTranslation();

    const [importTemplate] = useImportTemplateMutation();
    const [createFormFromTemplate] = useCreateFormFromTemplateMutation();

    const { data, isLoading } = useGetTemplateByIdQuery({
        template_id: templateId
    });

    const handleClickBack = () => {
        router.push(`/${workspace.workspaceName}/dashboard/templates`);
    };

    const request = {
        workspace_id: workspace.id,
        template_id: templateId
    };

    const handleImportTemplate = async () => {
        try {
            const response: any = await importTemplate(request);
            if (response?.data) {
                toast('Imported Successfully', { type: 'success' });
                await router.replace(`/${workspace.workspaceName}/dashboard/templates`);
            } else {
                toast('Error Occurred').toString(), { type: 'error' };
            }
        } catch (err) {
            toast('Error Occurred').toString(), { type: 'error' };
        }
    };

    const handleUseTemplate = async () => {
        try {
            const response: any = await createFormFromTemplate(request);
            if (response?.data) {
                toast('Created Form Successfully', { type: 'success' });
                await router.replace(`/${workspace.workspaceName}/dashboard/forms/${response?.data?.formId}/edit`);
            } else {
                toast('Error Occurred').toString(), { type: 'error' };
            }
        } catch (err) {
            toast('Error Occurred').toString(), { type: 'error' };
        }
    };

    // @ts-ignore
    return (
        <Layout showNavbar className={'bg-white !px-0'} childClassName={'!h-screen'}>
            <NextSeo title={data?.title + ' | ' + workspace.workspaceName} noindex={false} nofollow={false} />
            <div className={'py-3 px-5 flex justify-between items-center'}>
                <div className="flex items-center gap-1 pt-0 md:pt-2 cursor-pointer" onClick={handleClickBack}>
                    <ChevronForward className=" rotate-180 h-6 w-6  p-[2px]" />
                    <p className={'text-sm text-black-700 font-normal'}>{t('BUTTON.BACK')}</p>
                </div>
                <div className={'flex flex-row gap-1 md:gap-4'}>
                    {data?.workspaceId === workspace.id ? (
                        <AppButton icon={<SettingsIcon className={'text-brand-500'} />} variant={ButtonVariant.Ghost} onClick={() => openBottomSheetModal('TEMPLATE_SETTINGS_FULL_MODAL_VIEW', { template: data })}>
                            {t('SETTINGS')}
                        </AppButton>
                    ) : (
                        <AppButton variant={ButtonVariant.Secondary} onClick={handleImportTemplate}>
                            {t('TEMPLATE.BUTTONS.IMPORT_TEMPLATE')}
                        </AppButton>
                    )}
                    <AppButton onClick={handleUseTemplate}> {t('TEMPLATE.BUTTONS.USE_TEMPLATE')}</AppButton>
                </div>
            </div>
            {data && <BetterCollectedForm form={convertFormTemplateToStandardForm(data)} />}
        </Layout>
    );
};

export default SingleTemplate;

export async function getServerSideProps(_context: any) {
    const props = await getAuthUserPropsWithWorkspace(_context);
    const { template_id } = _context.params;
    if (!props.props) {
        return props;
    }
    const globalProps = props.props;
    return {
        props: {
            ...globalProps,
            templateId: template_id
        }
    };
}

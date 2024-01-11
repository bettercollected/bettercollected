import React from 'react';

import {useTranslation} from 'next-i18next';
import {NextSeo} from 'next-seo';
import {useRouter} from 'next/router';
import SettingsIcon from '@Components/Common/Icons/Common/Settings';
import AppButton from '@Components/Common/Input/Button/AppButton';
import {ButtonVariant} from '@Components/Common/Input/Button/AppButtonProps';
import BetterCollectedForm from '@Components/Form/BetterCollectedForm';
import {useBottomSheetModal} from '@Components/Modals/Contexts/BottomSheetModalContext';
import {toast} from 'react-toastify';

import {ChevronForward} from '@app/components/icons/chevron-forward';
import Layout from '@app/layouts/_layout';
import {getAuthUserPropsWithWorkspace} from '@app/lib/serverSideProps';
import {
    useCreateFormFromTemplateMutation,
    useGetTemplateByIdQuery,
    useImportTemplateMutation
} from '@app/store/template/api';
import {convertFormTemplateToStandardForm} from '@app/utils/convertDataType';
import EditTemplateButton from "@Components/Template/EditTemplateButton";
import MenuDropdown from "@Components/Common/Navigation/MenuDropdown/MenuDropdown";
import EllipsisOption from "@Components/Common/Icons/Common/EllipsisOption";
import {ListItemIcon, MenuItem} from "@mui/material";
import {useIsMobile} from "@app/lib/hooks/use-breakpoint";
import EditIcon from "@Components/Common/Icons/Common/Edit";
import {ArrowUp} from "@app/components/icons/arrow-up";

const SingleTemplate = (props: any) => {
    const {workspace, notFound, templateId} = props;
    const router = useRouter();
    const {openBottomSheetModal} = useBottomSheetModal();
    const {t} = useTranslation();
    const isMobile = useIsMobile();

    const [importTemplate] = useImportTemplateMutation();
    const [createFormFromTemplate] = useCreateFormFromTemplateMutation();

    const {data, isLoading} = useGetTemplateByIdQuery({
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
                toast('Imported Successfully', {type: 'success'});
                await router.replace(`/${workspace.workspaceName}/dashboard/templates`);
            } else {
                toast('Error Occurred').toString(), {type: 'error'};
            }
        } catch (err) {
            toast('Error Occurred').toString(), {type: 'error'};
        }
    };

    const handleUseTemplate = async () => {
        try {
            const response: any = await createFormFromTemplate(request);
            if (response?.data) {
                toast('Created Form Successfully', {type: 'success'});
                await router.replace(`/${workspace.workspaceName}/dashboard/forms/${response?.data?.formId}/edit`);
            } else {
                toast('Error Occurred').toString(), {type: 'error'};
            }
        } catch (err) {
            toast('Error Occurred').toString(), {type: 'error'};
        }
    };

    const handleEditTemplate = () => {
        router.push(`/${workspace.workspaceName}/templates/${templateId}/edit`);
    };

    const handleClickSetting = () => {
        openBottomSheetModal('TEMPLATE_SETTINGS_FULL_MODAL_VIEW', {template: data})
    }

    // @ts-ignore
    return (
        <Layout showNavbar className={'bg-white !px-0'} childClassName={'!h-screen'}>
            <NextSeo title={data?.title + ' | ' + workspace.workspaceName} noindex={false} nofollow={false}/>
            <div className={'py-3 px-5 flex justify-between items-center'}>
                <div className="flex items-center gap-1 pt-0 md:pt-2 cursor-pointer" onClick={handleClickBack}>
                    <ChevronForward className=" rotate-180 h-6 w-6  p-[2px]"/>
                    <p className={'text-sm text-black-700 font-normal'}>{t('BUTTON.BACK')}</p>
                </div>
                <div className={'flex flex-row gap-1 md:gap-4'}>
                    {!isMobile ? <>
                            {data?.workspaceId === workspace.id ? (
                                <AppButton icon={<SettingsIcon className={'text-brand-500'}/>} variant={ButtonVariant.Ghost}
                                           onClick={handleClickSetting}>
                                    {t('SETTINGS')}
                                </AppButton>
                            ) : (
                                <AppButton variant={ButtonVariant.Secondary} onClick={handleImportTemplate}>
                                    {t('TEMPLATE.BUTTONS.IMPORT_TEMPLATE')}
                                </AppButton>
                            )}
                            <EditTemplateButton templateId={templateId}/>
                            <AppButton onClick={handleUseTemplate}> {t('TEMPLATE.BUTTONS.USE_TEMPLATE')}</AppButton>
                        </>
                        :
                        <>
                            <AppButton onClick={handleUseTemplate}> {t('TEMPLATE.BUTTONS.USE_TEMPLATE')}</AppButton>
                            <MenuDropdown
                                width={180}
                                showExpandMore={false}
                                id="template-options"
                                menuTitle={''}
                                showIconBtnEffect
                                PaperProps={{
                                    sx: {
                                        boxShadow: '0px 0px 12px 0px rgba(7, 100, 235, 0.45)'
                                    }
                                }}
                                menuContent={
                                    <div>
                                        <EllipsisOption/>
                                    </div>
                                }
                            >
                                <MenuItem onClick={handleEditTemplate} className="body4">
                                    <ListItemIcon>
                                        <EditIcon/>
                                    </ListItemIcon>
                                    <span>{t('BUTTON.EDIT')}</span>
                                </MenuItem>
                                <MenuItem
                                    onClick={data?.workspaceId === workspace.id ? handleClickSetting : handleImportTemplate}
                                    className="body4"
                                >
                                    <ListItemIcon>
                                        {data?.workspaceId === workspace.id ? (
                                            <SettingsIcon/>
                                        ) : (
                                            <ArrowUp height={16} width={16}/>)}
                                    </ListItemIcon>
                                    <span>{data?.workspaceId === workspace.id ? t('SETTINGS') : t('TEMPLATE.BUTTONS.IMPORT_TEMPLATE')}</span>
                                </MenuItem>
                            </MenuDropdown>
                        </>
                    }
                </div>
            </div>
            {data && <BetterCollectedForm form={convertFormTemplateToStandardForm(data)}/>}
        </Layout>
    );
};

export default SingleTemplate;

export async function getServerSideProps(_context: any) {
    const props = await getAuthUserPropsWithWorkspace(_context);
    const {template_id} = _context.params;
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

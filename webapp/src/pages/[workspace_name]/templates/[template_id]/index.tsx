import React from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { useRouter } from 'next/router';

import { template } from 'lodash';

import EditIcon from '@Components/Common/Icons/Common/Edit';
import EllipsisOption from '@Components/Common/Icons/Common/EllipsisOption';
import SettingsIcon from '@Components/Common/Icons/Common/Settings';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import BetterCollectedForm from '@Components/Form/BetterCollectedForm';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import EditTemplateButton from '@Components/Template/EditTemplateButton';
import { ListItemIcon, MenuItem } from '@mui/material';
import { toast } from 'react-toastify';

import FormRenderer from '@app/components/form/renderer/form-renderer';
import { ArrowUp } from '@app/components/icons/arrow-up';
import { ChevronForward } from '@app/components/icons/chevron-forward';
import environments from '@app/configs/environments';
import Layout from '@app/layouts/_layout';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { useCreateFormFromTemplateMutation, useGetTemplateByIdQuery, useImportTemplateMutation } from '@app/store/template/api';
import { convertFormTemplateToStandardForm } from '@app/utils/convertDataType';
import { StandardFormDto } from '@app/models/dtos/form';
import { IFormTemplateDto } from '@app/models/dtos/template';
import LayoutWrapper from '@app/views/organism/Layout/LayoutWrapper';
import WelcomePage from '@app/views/organism/Form/WelcomePage';
import FormSlidePreview from '@app/views/organism/FormPreview/FormSlidePreview';
import SlideBuilder from '@app/views/organism/FormBuilder/SlideBuilder';

const SingleTemplate = (props: any) => {
    const { workspace, templateId } = props;
    const router = useRouter();
    const { openBottomSheetModal } = useBottomSheetModal();
    const { t } = useTranslation();
    const isMobile = useIsMobile();

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
                const editFormUrl = `/${workspace.workspaceName}/dashboard/forms/${response?.data?.formId}/edit`;
                if (response?.data?.builderVersion === 'v2') {
                    router.push(environments.HTTP_SCHEME + environments.DASHBOARD_DOMAIN + editFormUrl);
                } else {
                    router.push(editFormUrl);
                }
            } else {
                toast('Error Occurred').toString(), { type: 'error' };
            }
        } catch (err) {
            toast('Error Occurred').toString(), { type: 'error' };
        }
    };

    const handleEditTemplate = () => {
        router.push(`/${workspace.workspaceName}/templates/${templateId}/edit`);
    };

    const handleClickSetting = () => {
        openBottomSheetModal('TEMPLATE_SETTINGS_FULL_MODAL_VIEW', { template: data });
    };

    // @ts-ignore
    return (
        <Layout showNavbar className={'bg-white !px-0'} childClassName={'!h-screen'}>
            <NextSeo title={data?.title + ' | ' + workspace.workspaceName} noindex={false} nofollow={false} />
            <div className={'flex items-center justify-between px-5 py-3'}>
                <div className="flex cursor-pointer items-center gap-1 pt-0 md:pt-2" onClick={handleClickBack}>
                    <ChevronForward className=" h-6 w-6 rotate-180  p-[2px]" />
                    <p className={'text-black-700 text-sm font-normal'}>{t('BUTTON.BACK')}</p>
                </div>
                <div className={'flex flex-row gap-1 md:gap-4'}>
                    {!isMobile ? (
                        <>
                            {
                                data?.workspaceId === workspace.id && (
                                    <AppButton icon={<SettingsIcon className={'text-brand-500'} />} variant={ButtonVariant.Ghost} onClick={handleClickSetting}>
                                        {t('SETTINGS')}
                                    </AppButton>
                                )
                                // : (
                                //     <AppButton variant={ButtonVariant.Secondary} onClick={handleImportTemplate}>
                                //         {t('TEMPLATE.BUTTONS.IMPORT_TEMPLATE')}
                                //     </AppButton>
                                // )
                            }
                            {/* {data?.builderVersion !== 'v2' && <EditTemplateButton templateId={templateId} />}
                            <AppButton onClick={handleUseTemplate}> {t('TEMPLATE.BUTTONS.USE_TEMPLATE')}</AppButton> */}
                        </>
                    ) : (
                        <>
                            {/* <AppButton onClick={handleUseTemplate}> {t('TEMPLATE.BUTTONS.USE_TEMPLATE')}</AppButton> */}
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
                                        <EllipsisOption />
                                    </div>
                                }
                            >
                                {/* <MenuItem onClick={handleEditTemplate} className="body4">
                                    <ListItemIcon>
                                        <EditIcon />
                                    </ListItemIcon>
                                    <span>{t('BUTTON.EDIT')}</span>
                                </MenuItem> */}
                                {data?.workspaceId === workspace.id && (
                                    <MenuItem onClick={data?.workspaceId === workspace.id ? handleClickSetting : handleImportTemplate} className="body4">
                                        <ListItemIcon>{data?.workspaceId === workspace.id ? <SettingsIcon /> : <ArrowUp height={16} width={16} />}</ListItemIcon>
                                        <span>{data?.workspaceId === workspace.id ? t('SETTINGS') : t('TEMPLATE.BUTTONS.IMPORT_TEMPLATE')}</span>
                                    </MenuItem>
                                )}
                            </MenuDropdown>
                        </>
                    )}
                </div>
            </div>
            {data && (data.builderVersion === 'v2' ? <TemplatePreview template={data} /> : <FormRenderer isDisabled form={convertFormTemplateToStandardForm(data)} />)}
        </Layout>
    );
};

const TemplatePreview = ({ template }: { template: IFormTemplateDto }) => {
    return (
        <div className="flex !h-full w-full flex-row overflow-hidden  md:px-20">
            <div className="flex flex-wrap items-start justify-center md:justify-start  gap-2">
                {template?.fields?.map((slide) => (
                    <div className="mb-2 flex w-min cursor-pointer flex-col  rounded-lg border border-transparent p-1 hover:border-pink-500" key={slide?.id}>
                        <div className="border-black-300 relative aspect-video w-[250px] md:w-[500px] overflow-hidden rounded-md border">
                            <div className="pointer-events-none h-[720px] w-[1280px] scale-[0.1953] md:scale-[0.39]" style={{ transformOrigin: 'top left' }}>
                                <FormSlidePreview slide={slide} theme={template.theme} />
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
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

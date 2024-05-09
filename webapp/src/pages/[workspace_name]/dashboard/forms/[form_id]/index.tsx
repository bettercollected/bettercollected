import React, { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import PrivateFormButtonWrapper from '@Components/Common/FormVisibility/PrivateFormButtonWrapper';
import EditIcon from '@Components/Common/Icons/Common/Edit';
import SettingsIcon from '@Components/Common/Icons/Common/Settings';
import FormProviderIcon from '@Components/Common/Icons/Form/FormProviderIcon';
import Preview from '@Components/Common/Icons/Form/Preview';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { Group, IntegrationInstructions, Share } from '@mui/icons-material';

import FormIntegrations from '@app/components/form/integrations';
import { ChevronForward } from '@app/components/icons/chevron-forward';
import { HistoryIcon } from '@app/components/icons/history';
import { TrashIcon } from '@app/components/icons/trash';
import { useModal } from '@app/components/modal-views/context';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';
import environments from '@app/configs/environments';
import { breadcrumbsItems } from '@app/constants/locales/breadcrumbs-items';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { formPage } from '@app/constants/locales/form-page';
import Layout from '@app/layouts/_layout';
import { useBreakpoint, useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { StandardFormDto } from '@app/models/dtos/form';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import Error from '@app/pages/_error';
import { Button } from '@app/shadcn/components/ui/button';
import { Sheet, SheetClose, SheetContent, SheetFooter, SheetTrigger } from '@app/shadcn/components/ui/sheet';
import { resetSingleForm, selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { selectWorkspace } from '@app/store/workspaces/slice';
import getFormShareURL from '@app/utils/formUtils';
import { getEditFormURL } from '@app/utils/urlUtils';
import { validateFormOpen } from '@app/utils/validationUtils';
import PlayIcon from '@app/views/atoms/Icons/PlayIcon';
import BackButton from '@app/views/molecules/FormBuilder/BackButton';
import PreviewWrapper from '@app/views/molecules/FormBuilder/PreviewWrapper';
import PublishButton from '@app/views/molecules/FormBuilder/PublishButton';
import Form from '@app/views/organism/Form/Form';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';

const FormResponses = dynamic(() => import('@app/components/form/responses'));
const FormResponsesTable = dynamic(() => import('@app/components/datatable/form/form-responses'));
const FormVisibilities = dynamic(() => import('@app/components/form/visibility'));
const FormLinks = dynamic(() => import('@app/components/form/links'));
const FormSettings = dynamic(() => import('@app/components/form/settings'));
const FormPreview = dynamic(() => import('@app/components/form/preview'));

export default function FormPage(props: any) {
    const { form }: { form: StandardFormDto } = props;
    const { t } = useTranslation();
    const dispatch = useAppDispatch();
    const reduxStoreForm = useAppSelector(selectForm);
    const breakpoint = useBreakpoint();
    const router = useRouter();
    const { openModal } = useModal();
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const workspace = useAppSelector(selectWorkspace);
    const workspaceForm = useAppSelector(selectForm);

    const isMobile = useIsMobile();
    const paramTabs = [
        {
            icon: <Preview className="h-5 w-5" />,
            title: t(formConstant.preview),
            path: 'Preview'
        },
        {
            icon: <SettingsIcon className="h-5 w-5" />,
            title: t(localesCommon.settings),
            path: 'Settings'
        }
    ];

    const isFormOpen = validateFormOpen(reduxStoreForm?.settings?.formCloseDate);

    useEffect(() => {
        dispatch(setForm(props.form));
        return () => {
            dispatch(resetSingleForm());
        };
    }, [props.form]);

    if (!props && Object.keys(props).length === 0) {
        return <Error />;
    }

    const breadcrumbsItem: Array<BreadcrumbsItem> = [
        {
            title: t(breadcrumbsItems.dashboard),
            url: `/${props?.workspace?.workspaceName}/dashboard`
        },
        {
            title: t(breadcrumbsItems.forms),
            url: `/${props?.workspace?.workspaceName}/dashboard/forms`
        },
        {
            title: router.query ? router.query.view?.toString() ?? 'Preview' : 'Preview',
            disabled: true
        }
    ];

    if (form?.isPublished) {
        const additionalTabs = [
            {
                icon: <HistoryIcon className="h-5 w-5" />,
                title: t(formConstant.responders) + ' (' + form.responses + ')',
                path: 'Responses'
            },
            {
                icon: <TrashIcon className="h-5 w-5" />,
                title: t(formConstant.deletionRequests) + ' (' + form.deletionRequests + ')',
                path: 'Deletion Request'
            },
            {
                icon: <Group className="h-5 w-5" />,
                title: t(formConstant.settings.visibility.title),
                path: 'FormVisibility'
            }
        ];

        if (form?.settings?.provider === 'self' && environments.ENABLE_ACTIONS)
            additionalTabs.splice(0, 0, {
                icon: <IntegrationInstructions className="h-5 w-5" />,
                title: 'Integrations',
                path: 'Integrations'
            });
        paramTabs.splice(2, 0, ...additionalTabs);

        if (isFormOpen) {
            paramTabs.splice(6, 0, {
                icon: <Group className="h-5 w-5" />,
                title: t(formConstant.settings.formLink.title),
                path: 'FormLinks'
            });
        }
    }

    const handleBackClick = async () => {
        await router.push(`/${props.workspace.workspaceName}/dashboard/forms`);
    };

    if (!form?.formId) {
        return <></>;
    }

    return (
        <Layout isCustomDomain={false} isClientDomain={false} showNavbar={true} hideMenu={false} showAuthAccount={true} className="flex w-full flex-col !bg-white !p-0">
            <NextSeo title={form.title} noindex={true} nofollow={true} />
            <div className="my-2  w-full ">
                <div className="mt-12 flex flex-col gap-1">
                    <FormPageLayer className=" px-4 md:px-10 lg:px-28 ">
                        <div className="flex justify-between">
                            <div className="flex flex-row items-center gap-1">
                                {isMobile && <ChevronForward onClick={handleBackClick} className=" h-6 w-6 rotate-180 cursor-pointer p-[2px] " />}
                                {isMobile ? <h1 className="hp3-new">{form?.title}</h1> : <h1 className="h2-new text-pink ">{form?.title}</h1>}
                            </div>
                            <div className="hidden gap-4 lg:flex">
                                {form?.settings?.provider === 'self' && form?.builderVersion === 'v2' && (
                                    <AppButton
                                        icon={<EditIcon className="h-6 w-6" />}
                                        variant={['sm', 'md', 'lg', 'xl', '2xl'].indexOf(breakpoint) !== -1 ? ButtonVariant.Secondary : ButtonVariant.Ghost}
                                        className="!px-0 sm:!px-5"
                                        onClick={() => {
                                            router.push(getEditFormURL(workspace, form));
                                        }}
                                    >
                                        <span className="hidden sm:block">{t(formPage.editForm)}</span>
                                    </AppButton>
                                )}
                                {form?.isPublished && isFormOpen && (
                                    <PrivateFormButtonWrapper isPrivate={workspaceForm?.settings?.hidden}>
                                        <AppButton
                                            variant={['sm', 'md', 'lg', 'xl', '2xl'].indexOf(breakpoint) !== -1 ? ButtonVariant.Primary : ButtonVariant.Ghost}
                                            icon={<Share />}
                                            className="!px-0 sm:!px-5"
                                            disabled={workspaceForm?.settings?.hidden}
                                            onClick={() =>
                                                openModal('SHARE_VIEW', {
                                                    url: getFormShareURL(workspaceForm, workspace),
                                                    title: t(formConstant.shareThisForm)
                                                })
                                            }
                                        >
                                            <span className="hidden sm:block">{t(formPage.shareForm)}</span>
                                        </AppButton>
                                    </PrivateFormButtonWrapper>
                                )}
                            </div>
                            <div className="flex gap-4 lg:hidden">
                                <Button
                                    icon={<PlayIcon />}
                                    onClick={() => {
                                        openFullScreenModal('PREVIEW_MODAL');
                                    }}
                                    variant={'v2Button'}
                                >
                                    Preview
                                </Button>

                                {form?.isPublished ? (
                                    <PrivateFormButtonWrapper isPrivate={workspaceForm?.settings?.hidden}>
                                        <Button
                                            variant={'primary'}
                                            icon={<Share />}
                                            className="!px-0 sm:!px-5"
                                            disabled={workspaceForm?.settings?.hidden}
                                            onClick={() =>
                                                openModal('SHARE_VIEW', {
                                                    url: getFormShareURL(workspaceForm, workspace),
                                                    title: t(formConstant.shareThisForm)
                                                })
                                            }
                                        >
                                            <span className="hidden sm:block">{'Share'}</span>
                                        </Button>
                                    </PrivateFormButtonWrapper>
                                ) : (
                                    <PublishButton />
                                )}
                            </div>
                        </div>
                        <div className="flex flex-row items-center gap-1">
                            <FormProviderIcon provider={form?.settings?.provider} />
                        </div>
                        <Divider className="mt-6 hidden md:flex" />
                    </FormPageLayer>
                    <Divider className="mt-6 flex md:hidden" />

                    <ParamTab showInfo={true} className="md:px-10 lg:px-28" tabMenu={paramTabs}>
                        <FormPageLayer className="px-4 md:px-10 lg:px-28">
                            <TabPanel className="focus:outline-none" key="Preview">
                                <FormPreview />
                            </TabPanel>
                        </FormPageLayer>
                        <FormPageLayer className="px-2 md:px-32">
                            <TabPanel className="focus:outline-none" key="Settings">
                                <FormSettings />
                            </TabPanel>
                        </FormPageLayer>
                        {form?.isPublished && (
                            <>
                                {form?.settings?.provider === 'self' && environments.ENABLE_ACTIONS && (
                                    <TabPanel className="focus:outline-none" key="Integrations">
                                        <FormIntegrations />
                                    </TabPanel>
                                )}
                                <TabPanel className="focus:outline-none" key="Responses">
                                    <FormResponses />
                                </TabPanel>
                                <TabPanel className="focus:outline-none" key="Deletion Requests">
                                    <FormResponsesTable props={{ workspace, requestForDeletion: true }} />
                                </TabPanel>
                            </>
                        )}
                        <FormPageLayer className="px-2 md:px-32">
                            {form?.isPublished ? (
                                <>
                                    <TabPanel className="focus:outline-none" key="FormVisibility">
                                        <FormVisibilities />
                                    </TabPanel>
                                    {isFormOpen && (
                                        <TabPanel className="focus:outline-none" key="FormLinks">
                                            <FormLinks />
                                        </TabPanel>
                                    )}
                                </>
                            ) : (
                                <></>
                            )}
                        </FormPageLayer>
                    </ParamTab>
                </div>
            </div>
        </Layout>
    );
}
export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';

interface IFormPageLayerProps {
    children: React.ReactNode;
    className?: string;
}

const FormPageLayer = ({ children, className }: IFormPageLayerProps) => {
    return <div className={className}>{children}</div>;
};

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
import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
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
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { StandardFormDto } from '@app/models/dtos/form';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import Error from '@app/pages/_error';
import { resetSingleForm, selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getFormUrl } from '@app/utils/urlUtils';
import { validateFormOpen } from '@app/utils/validationUtils';

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
    const locale = props._nextI18Next.initialLocale === 'en' ? '' : `${props._nextI18Next.initialLocale}/`;
    const breakpoint = useBreakpoint();
    const router = useRouter();
    const { openModal } = useModal();
    const workspace = useAppSelector(selectWorkspace);
    const workspaceForm = useAppSelector(selectForm);
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
            url: `/${locale}${props?.workspace?.workspaceName}/dashboard`
        },
        {
            title: t(breadcrumbsItems.forms),
            url: `/${locale}${props?.workspace?.workspaceName}/dashboard/forms`
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

    return (
        <Layout isCustomDomain={false} isClientDomain={false} showNavbar={true} hideMenu={false} showAuthAccount={true} className="!p-0 !bg-white flex flex-col w-full">
            <NextSeo title={form.title} noindex={true} nofollow={true} />
            <div className="w-full  my-2 ">
                <div className="flex w-full items-center gap-1 px-5">
                    <ChevronForward onClick={handleBackClick} className=" cursor-pointer rotate-180 h-6 w-6 p-[2px] " />
                    <BreadcrumbsRenderer items={breadcrumbsItem} />
                </div>
                <div className="flex flex-col gap-1 mt-12">
                    <FormPageLayer className=" lg:px-28 md:px-10 px-4 ">
                        <div className="flex justify-between">
                            <h1 className="h2-new !text-pink">{form?.title}</h1>
                            <div className="flex gap-4">
                                {form?.settings?.provider === 'self' && (
                                    <AppButton
                                        icon={<EditIcon className="h-6 w-6" />}
                                        variant={['sm', 'md', 'lg', 'xl', '2xl'].indexOf(breakpoint) !== -1 ? ButtonVariant.Secondary : ButtonVariant.Ghost}
                                        className="!px-0 sm:!px-5"
                                        onClick={() => {
                                            router.push(`/${workspace.workspaceName}/dashboard/forms/${form.formId}/edit`);
                                        }}
                                    >
                                        <span className="sm:block hidden">{t(formPage.editForm)}</span>
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
                                                    url: getFormUrl(workspaceForm, workspace),
                                                    title: t(formConstant.shareThisForm)
                                                })
                                            }
                                        >
                                            <span className="sm:block hidden">{t(formPage.shareForm)}</span>
                                        </AppButton>
                                    </PrivateFormButtonWrapper>
                                )}
                            </div>
                        </div>
                        <div className="flex gap-1 flex-row items-center">
                            <FormProviderIcon provider={form?.settings?.provider} />
                        </div>
                        <Divider className="mt-6 hidden md:flex" />
                    </FormPageLayer>
                    <Divider className="mt-6 flex md:hidden" />

                    <ParamTab showInfo={true} className=" lg:px-28 md:px-10 " tabMenu={paramTabs}>
                        <FormPageLayer className="w-full">
                            <TabPanel className="focus:outline-none" key="Preview">
                                <FormPreview />
                            </TabPanel>
                        </FormPageLayer>
                        <FormPageLayer className="md:px-32 px-2">
                            <TabPanel className="focus:outline-none" key="Settings">
                                <FormSettings />
                            </TabPanel>
                        </FormPageLayer>
                        {form?.isPublished && (
                            <>
                                {form?.settings?.provider === 'self' && (
                                    <TabPanel className="focus:outline-none" key="Integrations">
                                        <FormIntegrations />
                                    </TabPanel>
                                )}
                                <TabPanel className="focus:outline-none" key="Responses">
                                    <FormResponses />
                                </TabPanel>
                            </>
                        )}
                        <FormPageLayer className="md:px-32 px-2">
                            {form?.isPublished ? (
                                <>
                                    <TabPanel className="focus:outline-none" key="Deletion Requests">
                                        <FormResponsesTable props={{ workspace, requestForDeletion: true }} />
                                    </TabPanel>
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

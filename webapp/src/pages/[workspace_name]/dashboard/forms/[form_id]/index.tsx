import React, {useEffect} from 'react';

import {useTranslation} from 'next-i18next';
import {NextSeo} from 'next-seo';
import {useRouter} from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import EditIcon from '@Components/Common/Icons/Edit';
import Preview from '@Components/Common/Icons/Preview';
import SettingsIcon from '@Components/Common/Icons/Settings';
import SmallLogo from '@Components/Common/Icons/SmallLogo';
import AppButton from '@Components/Common/Input/Button/AppButton';
import {ButtonVariant} from '@Components/Common/Input/Button/AppButtonProps';
import {Group, Share} from '@mui/icons-material';

import FormResponsesTable from '@app/components/datatable/form/form-responses';
import FormGroups from '@app/components/form/groups';
import FormPreview from '@app/components/form/preview';
import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import FormResponses from '@app/components/form/responses';
import FormSettings from '@app/components/form/settings';
import {ChevronForward} from '@app/components/icons/chevron-forward';
import {HistoryIcon} from '@app/components/icons/history';
import {TrashIcon} from '@app/components/icons/trash';
import {useModal} from '@app/components/modal-views/context';
import ParamTab, {TabPanel} from '@app/components/ui/param-tab';
import {breadcrumbsItems} from '@app/constants/locales/breadcrumbs-items';
import {localesCommon} from '@app/constants/locales/common';
import {formConstant} from '@app/constants/locales/form';
import {groupConstant} from '@app/constants/locales/group';
import Layout from '@app/layouts/_layout';
import {useBreakpoint} from '@app/lib/hooks/use-breakpoint';
import {StandardFormDto} from '@app/models/dtos/form';
import {BreadcrumbsItem} from '@app/models/props/breadcrumbs-item';
import Error from '@app/pages/_error';
import {setForm} from '@app/store/forms/slice';
import {useAppDispatch, useAppSelector} from '@app/store/hooks';
import {selectWorkspace} from '@app/store/workspaces/slice';
import {getFormUrl} from '@app/utils/urlUtils';

export default function FormPage(props: any) {
    const { form }: { form: StandardFormDto } = props;

    const { t } = useTranslation();
    const dispatch = useAppDispatch();
    const locale = props._nextI18Next.initialLocale === 'en' ? '' : `${props._nextI18Next.initialLocale}/`;
    const breakpoint = useBreakpoint();
    const router = useRouter();
    const { openModal } = useModal();
    const workspace = useAppSelector(selectWorkspace);

    useEffect(() => {
        dispatch(setForm(props.form));
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
        },
        {
            icon: <Group className="h-5 w-5" />,
            title: t(groupConstant.groups) + ' (' + form.groups?.length + ')',
            path: 'Groups'
        },
        {
            icon: <Group className="h-5 w-5" />,
            title: 'Form Visibility (' + form.groups?.length + ')',
            path: 'FormVisibility'
        },
        {
            icon: <Group className="h-5 w-5" />,
            title: 'Form Links (' + form.groups?.length + ')',
            path: 'FormLinks'
        }
    ];

    if (form?.isPublished) {
        paramTabs.splice(
            1,
            0,
            ...[
                {
                    icon: <HistoryIcon className="h-5 w-5" />,
                    title: t(formConstant.responses) + ' (' + form.responses + ')',
                    path: 'Responses'
                },
                {
                    icon: <TrashIcon className="h-5 w-5" />,
                    title: t(formConstant.deletionRequests) + ' (' + form.deletionRequests + ')',
                    path: 'Deletion Request'
                }
            ]
        );
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
                <div className="flex flex-col gap-1 mt-16">
                    <FormPageLayer className=" lg:px-28 md:px-10 px-4">
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
                                        <span className="sm:block hidden">Edit Form</span>
                                    </AppButton>
                                )}
                                <AppButton
                                    variant={['sm', 'md', 'lg', 'xl', '2xl'].indexOf(breakpoint) !== -1 ? ButtonVariant.Primary : ButtonVariant.Ghost}
                                    icon={<Share />}
                                    className="!px-0 sm:!px-5"
                                    onClick={() =>
                                        openModal('SHARE_VIEW', {
                                            url: getFormUrl(form, workspace),
                                            title: t(formConstant.shareThisForm)
                                        })
                                    }
                                >
                                    <span className="sm:block hidden">Share Form</span>
                                </AppButton>
                            </div>
                        </div>
                        <div className="flex gap-1 flex-row items-center">
                            <SmallLogo className="h-6 w-6" />
                            <h1 className="text-black-600 text-sm">bettercollected</h1>
                        </div>
                        <Divider className="mt-6" />
                    </FormPageLayer>

                    <ParamTab showInfo={true} className="mb-[38px] pb-0 lg:px-28 md:px-10  px-4" tabMenu={paramTabs}>
                        <FormPageLayer className="w-full">
                            <TabPanel className="focus:outline-none" key="Preview">
                                <FormPreview />
                            </TabPanel>
                        </FormPageLayer>
                        <FormPageLayer className="md:px-32 px-10">
                            {form?.isPublished ? (
                                <>
                                    <TabPanel className="focus:outline-none" key="Responses">
                                        <FormResponses />
                                    </TabPanel>
                                    <TabPanel className="focus:outline-none" key="Deletion Requests">
                                        <FormResponsesTable props={{ workspace, requestForDeletion: true }} />
                                    </TabPanel>
                                </>
                            ) : (
                                <></>
                            )}

                            <TabPanel className="focus:outline-none" key="Settings">
                                <FormSettings />
                            </TabPanel>
                            <TabPanel className="focus:outline-none" key="Groups">
                                <FormGroups />
                            </TabPanel>
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

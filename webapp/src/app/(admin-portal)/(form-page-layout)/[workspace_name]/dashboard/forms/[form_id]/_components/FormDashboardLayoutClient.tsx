'use client';

import cn from 'classnames';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import React, { useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import PrivateFormButtonWrapper from '@Components/Common/FormVisibility/PrivateFormButtonWrapper';
import FormProviderIcon from '@Components/Common/Icons/Form/FormProviderIcon';
import {
    BarChart,
    Blocks,
    ChevronRight,
    Edit2,
    Eye,
    History,
    Link2Icon,
    Play,
    Settings,
    Share2,
    Trash2
} from 'lucide-react';

import { useModal } from '@app/Components/modal-views/context';
import { useFullScreenModal } from '@app/Components/modal-views/full-screen-modal-context';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { formPage } from '@app/constants/locales/form-page';
import TopNavLayout from '@app/layouts/top-navbar-layout';
import { useBreakpoint, useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { StandardFormDto } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { resetSingleForm, selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import getFormShareURL from '@app/utils/formUtils';
import { getEditFormURL } from '@app/utils/urlUtils';
import { validateFormOpen } from '@app/utils/validationUtils';
import PublishButton from '@app/views/molecules/FormBuilder/PublishButton';
import FullScreenLoader from '@Components/ui/fullscreen-loader';

export default function FormDashboardLayoutClient({
    form,
    children,
    params
}: {
    form: StandardFormDto;
    children: React.ReactNode;
    params: { workspace_name: string; form_id: string }
}) {
    const { t } = useTranslation();
    const dispatch = useAppDispatch();
    const reduxStoreForm = useAppSelector(selectForm); // Check if this updates after dispatch(setForm(form))
    const breakpoint = useBreakpoint();
    const router = useRouter();
    const pathname = usePathname();
    const { openModal } = useModal();
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const workspace = useAppSelector(selectWorkspace);
    const workspaceForm = useAppSelector(selectForm);

    const isMobile = useIsMobile();
    const isFormOpen = validateFormOpen(reduxStoreForm?.settings?.formCloseDate);

    // Initial load set form
    useEffect(() => {
        dispatch(setForm(form));
        return () => {
            dispatch(resetSingleForm());
        };
    }, [form, dispatch]);


    const storeForm = useAppSelector(selectForm);



    const tabMenu = useMemo(() => {
        const tabs = [
            {
                icon: <Eye className="h-5 w-5" />,
                title: t(formConstant.preview),
                path: 'preview'
            },
            {
                icon: <Settings className="h-5 w-5" />,
                title: t(localesCommon.settings),
                path: 'settings'
            }
        ];

        if (form?.isPublished) {
            if (form?.settings?.provider === 'self' && form?.builderVersion === 'v2') {
                tabs.push({
                    icon: <Blocks className="h-5 w-5" />,
                    title: 'Integrations',
                    path: 'integrations'
                });
            }
            tabs.push({
                icon: <History className="h-5 w-5" />,
                title: t(formConstant.responders) + ' (' + form.responses + ')',
                path: 'responses'
            });
            tabs.push({
                icon: <Trash2 className="h-5 w-5" />,
                title: t(formConstant.deletionRequests) + ' (' + (form as any).deletionRequests + ')',
                path: 'deletion-requests'
            });
            tabs.push({
                icon: <Eye className="h-5 w-5" />,
                title: t(formConstant.settings.visibility.title),
                path: 'visibility'
            });

            if (isFormOpen) {
                tabs.push({
                    icon: <Link2Icon className="h-5 w-5" />,
                    title: t(formConstant.settings.formLink.title),
                    path: 'links'
                });
                tabs.push({
                    icon: <BarChart className="h-5 w-5" />,
                    title: 'Analytics',
                    path: 'analytics'
                });
            }
        }
        return tabs;
    }, [form, t, isFormOpen]);

    const handleBackClick = () => {
        router.push(`/${workspace?.workspaceName}/dashboard/forms`);
    };


    if (pathname.endsWith("/edit")) {
        return (
            <>{children}</>
        )
    }

    if (!form?.formId) {
        return <></>;
    }

    if (!storeForm?.formId) {
        return <FullScreenLoader />
    }

    return (
        <TopNavLayout isCustomDomain={false} isClientDomain={false} showNavbar={true} hideMenu={false} showAuthAccount={true} className="flex w-full flex-col !bg-white !p-0">
            <div className="my-2 w-full">
                <div className="mt-6 flex flex-col gap-1 sm:mt-12">
                    <FormPageLayer className="px-4 md:px-10 lg:px-28">
                        <div className="flex justify-between">
                            <div className="flex flex-row items-center gap-1 cursor-pointer" onClick={handleBackClick}>
                                {isMobile && <ChevronRight className="h-6 w-6 rotate-180 p-[2px]" />}
                                {isMobile ? <h1 className="hp3-new">{form?.title}</h1> : <h1 className="h2-new text-pink">{form?.title}</h1>}
                            </div>
                            <div className="hidden gap-4 lg:flex">
                                {form?.settings?.provider === 'self' && form?.builderVersion === 'v2' && (
                                    <Button
                                        icon={<Edit2 className="h-6 w-6" />}
                                        variant={['sm', 'md', 'lg', 'xl', '2xl'].indexOf(breakpoint) !== -1 ? 'secondary' : 'ghost'}
                                        className="!px-0 sm:!px-5"
                                        onClick={() => {
                                            router.push(getEditFormURL(workspace, form));
                                        }}
                                    >
                                        <span className="hidden sm:block">{t(formPage.editForm)}</span>
                                    </Button>
                                )}
                                {form?.isPublished && isFormOpen && (
                                    <PrivateFormButtonWrapper isPrivate={workspaceForm?.settings?.hidden}>
                                        <Button
                                            variant={['sm', 'md', 'lg', 'xl', '2xl'].indexOf(breakpoint) !== -1 ? 'primary' : 'ghost'}
                                            icon={<Share2 className="h-5 w-5" />}
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
                                        </Button>
                                    </PrivateFormButtonWrapper>
                                )}
                            </div>
                            <div className="flex gap-2 lg:hidden">
                                {form.builderVersion === 'v2' && (
                                    <Button
                                        icon={<Play className="h-5 w-5" />}
                                        onClick={() => {
                                            openFullScreenModal('PREVIEW_MODAL');
                                        }}
                                        className="text-[10px]"
                                        variant={'v2Button'}
                                    >
                                        Preview
                                    </Button>
                                )}

                                {form?.isPublished ? (
                                    <PrivateFormButtonWrapper isPrivate={workspaceForm?.settings?.hidden}>
                                        <Button
                                            variant={'primary'}
                                            icon={<Share2 className="h-5 w-5" />}
                                            disabled={workspaceForm?.settings?.hidden}
                                            onClick={() =>
                                                openModal('SHARE_VIEW', {
                                                    url: getFormShareURL(workspaceForm, workspace),
                                                    title: t(formConstant.shareThisForm)
                                                })
                                            }
                                        >
                                            <span className="">{'Share'}</span>
                                        </Button>
                                    </PrivateFormButtonWrapper>
                                ) : (
                                    <PublishButton refresh />
                                )}
                            </div>
                        </div>
                        {!isMobile && (
                            <div className="flex flex-row items-center gap-1 mb-4">
                                <FormProviderIcon provider={form.settings?.provider === 'self' && form.importedFormId && form.settings.showOriginalForm ? 'google' : form?.settings?.provider} />
                            </div>
                        )}
                        <Divider className="mt-6 hidden md:flex" />
                    </FormPageLayer>
                    <div className="md:px-10 lg:px-28 pt-4">
                        <div className="flex space-x-1 border-b border-gray-200 overflow-x-auto">
                            {tabMenu.map((tab) => {
                                const isActive = pathname?.includes(`/${tab.path}`);
                                return (
                                    <Link key={tab.path} href={`/${params.workspace_name}/dashboard/forms/${params.form_id}/${tab.path}`} className={cn(
                                        'flex items-center gap-2 px-4 py-2 text-sm font-medium cursor-pointer hover:bg-black-200 hover:rounded whitespace-nowrap',
                                        isActive
                                            ? 'border-b-2 border-black-900 text-black-900 bg-gray-100 rounded-t'
                                            : 'text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                    )}>
                                        {tab.icon}
                                        {tab.title}
                                    </Link>
                                );
                            })}
                        </div>
                    </div>
                    <div className="w-full pt-5">
                        {children}
                    </div>
                </div>
            </div>
        </TopNavLayout>
    );
}

const FormPageLayer = ({ children, className }: any) => {
    return <div className={className}>{children}</div>;
};

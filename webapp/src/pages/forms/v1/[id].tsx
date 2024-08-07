'use client';

import React, { useEffect, useRef } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { useRouter } from 'next/navigation';

import SmallLogo from '@Components/Common/Icons/Common/SmallLogo';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import HeaderImageWrapper from '@Components/Common/Wrapper/HeaderImageWrapper';
import BetterCollectedForm from '@Components/Form/BetterCollectedForm';
import { ChevronLeft } from '@mui/icons-material';
import { Widget } from '@typeform/embed-react';

import { useModal } from '@app/Components/modal-views/context';
import { useFullScreenModal } from '@app/Components/modal-views/full-screen-modal-context';
import FullScreenLoader from '@app/Components/ui/fullscreen-loader';
import ActiveLink from '@app/Components/ui/links/active-link';
import Loader from '@app/Components/ui/loader';
import PoweredBy from '@app/Components/ui/powered-by';
import environments from '@app/configs/environments';
import globalConstants from '@app/constants/global';
import { localesCommon } from '@app/constants/locales/common';
import Layout from '@app/layouts/_layout';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { selectAuth } from '@app/store/auth/slice';
import { resetSingleForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceFormQuery } from '@app/store/workspaces/api';
import { checkHasCustomDomain, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';
import { validateFormOpen } from '@app/utils/validationUtils';

export default function SingleFormPage(props: any) {
    const { back, slug, hasCustomDomain, workspace, form: fetched_form } = props;

    const { data, isLoading, error } = useGetWorkspaceFormQuery(
        {
            workspace_id: workspace.id,
            custom_url: slug,
            published: true
        },
        { skip: !!fetched_form?.formId || !workspace.id }
    );

    const dispatch = useAppDispatch();

    const auth = useAppSelector(selectAuth);

    const router = useRouter();
    const form: StandardFormDto | undefined = fetched_form?.formId ? fetched_form : data;

    const title = fetched_form?.title ?? workspace?.title;
    const description = fetched_form?.description?.slice(0, 100) ?? '';
    const url = globalConstants.socialPreview.url;

    const iframeRef = useRef(null);
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const { openModal, closeModal } = useModal();

    const responderUri = form?.settings?.embedUrl || '';
    const { t } = useTranslation();

    const isFormClosed = !validateFormOpen(form?.settings?.formCloseDate);

    const showBranding = !workspace?.isPro || !form?.settings?.disableBranding;

    useEffect(() => {
        if (form?.formId) {
            dispatch(setForm(form));
        }
        return () => {
            dispatch(resetSingleForm());
        };
    }, [form]);

    useEffect(() => {
        if (form?.settings?.provider && form.settings?.provider === 'google' && form?.fields && hasFileUpload(form?.fields)) {
            router.push(form?.settings?.embedUrl || '');
        }
        if (environments.ENABLE_COLLECT_EMAILS && form?.settings?.provider === 'self' && form?.settings?.requireVerifiedIdentity && auth?.is401) {
            openModal('SIGN_IN_TO_FILL_FORM', { nonClosable: true });
        }
        return () => {
            closeModal();
        };
    }, [form, auth]);

    if (data && isFormClosed)
        return (
            <HeaderImageWrapper>
                <div className="flex  flex-col items-center px-5">
                    <div className="h2-new text-black-800 mt-[60px] font-bold ">This Form Is Closed</div>
                    <div className="h4-new text-black-800 mt-4 text-center">The form &quot;{form?.title || 'Untitled'}&quot; is no longer accepting responses.</div>
                    <div className="p2-new text-black-700 mt-2 text-center text-sm">Try contacting the owner of the form if you think that this is a mistake.</div>
                </div>
                {showBranding && <PoweredBy />}
            </HeaderImageWrapper>
        );

    // @ts-ignore
    if (error && error?.status === 401) {
        return (
            <HeaderImageWrapper className="my-16">
                <span className="text-black-700 mb-5">You are trying to access a private form. Please login to continue.</span>
                <AppButton
                    size={ButtonSize.Medium}
                    onClick={() => {
                        openFullScreenModal('LOGIN_VIEW');
                    }}
                >
                    Login
                </AppButton>
            </HeaderImageWrapper>
        );
    }

    if (error) {
        return (
            <HeaderImageWrapper className="my-16 gap-4">
                <div className="flex flex-col items-center gap-2">
                    <span className="h4-new text-black-800">Error loading form!!</span>
                    <span className="p2-new text-black-700 text-center">Either the form does not exist or you do not have access to this form.</span>
                </div>
                <div
                    className={`mt-10 flex cursor-pointer items-center gap-2 rounded-md border-[2px] border-gray-200 bg-white px-3 py-2`}
                    onClick={() => {
                        router.push('https://bettercollected.com');
                    }}
                >
                    <SmallLogo className="h-6 w-6" />
                    <span className="body3 text-black-700">Try bettercollected</span>
                </div>
            </HeaderImageWrapper>
        );
    }

    if (isLoading) return <FullScreenLoader />;
    const hasFileUpload = (fields: Array<any>) => {
        let isUploadField = false;
        if (fields && Array.isArray(fields) && fields.length > 0) {
            fields.forEach((field: any) => {
                if (field && field?.type && field.type === 'file_upload') {
                    isUploadField = true;
                }
            });
            return isUploadField;
        }
        return isUploadField;
    };

    const goToForms = () => {
        let pathName = '/';
        if (!hasCustomDomain) {
            pathName = `/${workspace.workspaceName}`;
        }

        const obj = {
            pathname: pathName,
            query: { view: 'forms' }
        };

        // Convert object to URLSearchParams
        const params = new URLSearchParams(obj.query);

        // Create URL string
        const href = obj.pathname + '?' + params.toString();

        router.push(href, { scroll: true });
    };

    if (form?.settings?.provider && form.settings?.provider === 'google' && form?.fields && hasFileUpload(form?.fields)) {
        return <FullScreenLoader />;
    }

    // TODO: Update this component to be reusable
    if (form?.settings?.provider && form.settings?.provider === 'google' && form?.fields && hasFileUpload(form?.fields)) {
        return (
            <>
                <NextSeo
                    title={title}
                    description={description}
                    noindex={!environments.IS_IN_PRODUCTION_MODE}
                    nofollow={!environments.IS_IN_PRODUCTION_MODE}
                    openGraph={{
                        title: title,
                        description: description,
                        type: 'website',
                        locale: 'en_IE',
                        url,
                        site_name: title || globalConstants.appName,
                        images: [
                            {
                                url: fetched_form?.coverImage || workspace?.profileImage,
                                alt: title
                            }
                        ]
                    }}
                />
                <div className="relative !min-h-screen !bg-white">
                    {back && (
                        <div className="z-10 mt-5 flex w-auto cursor-pointer items-center gap-2 px-5 hover:!-translate-y-0 focus:-translate-y-0 lg:px-20" onClick={() => goToForms()}>
                            <ChevronLeft height={24} width={24} />
                            <span className="sh1">{t(localesCommon.forms)}</span>
                        </div>
                    )}
                    <div className="absolute bottom-0 left-0 right-0 top-16 w-full items-start justify-between rounded-lg bg-white !p-0">
                        <div className="flex flex-col items-center justify-between gap-8 p-10">
                            <div className="max-w-xs px-3 py-6 text-center">
                                <svg aria-hidden="true" className="mx-auto mb-4 h-14 w-14 text-yellow-500 dark:text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                </svg>
                                <h3 className="mb-5 text-lg font-bold text-gray-700 dark:text-gray-400">{form?.title}</h3>
                                <p className="mb-5 text-sm font-normal text-gray-500 dark:text-gray-400">{form?.description}</p>

                                <div className="mb-4 rounded-lg bg-yellow-50 px-4 py-10 text-sm text-yellow-800 dark:bg-gray-800 dark:text-yellow-300" role="alert">
                                    <span className="font-medium">Warning!</span> This form consists file upload. You may need to open it in a new tab to fill it out.
                                </div>
                                <ActiveLink
                                    href={responderUri}
                                    data-modal-hide="popup-modal"
                                    type="button"
                                    className="mr-2 inline-flex items-center rounded-lg bg-blue-500 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-400 focus:outline-none focus:ring-4 focus:ring-red-300 dark:focus:ring-red-800"
                                >
                                    Fill out the form
                                </ActiveLink>
                            </div>
                        </div>
                    </div>
                </div>
            </>
        );
    }

    if (form?.settings?.provider && form.settings?.provider === 'google') {
        return (
            <>
                <NextSeo
                    title={title}
                    description={description}
                    noindex={!environments.IS_IN_PRODUCTION_MODE}
                    nofollow={!environments.IS_IN_PRODUCTION_MODE}
                    openGraph={{
                        title: title,
                        description: description,
                        type: 'website',
                        locale: 'en_IE',
                        url,
                        site_name: title || globalConstants.appName,
                        images: [
                            {
                                url: fetched_form?.coverImage || workspace?.profileImage,
                                alt: title
                            }
                        ]
                    }}
                />
                <div className="relative !min-h-screen">
                    <div className="!m-0' absolute bottom-0 left-0 right-0 top-0 !p-0">
                        {form?.settings?.provider === 'google' && !!responderUri && (
                            <iframe ref={iframeRef} src={`${responderUri}?embedded=true`} width="100%" height="100%" frameBorder="0">
                                <Loader />
                            </iframe>
                        )}
                    </div>
                </div>
            </>
        );
    }

    const isFormDisabled = environments.ENABLE_COLLECT_EMAILS && form?.settings?.requireVerifiedIdentity && !auth.email;
    return (
        <Layout showNavbar={false} isCustomDomain={hasCustomDomain} isClientDomain={!hasCustomDomain} showAuthAccount={true} className="relative !min-h-screen !bg-white">
            <NextSeo
                title={title}
                description={description}
                noindex={!environments.IS_IN_PRODUCTION_MODE}
                nofollow={!environments.IS_IN_PRODUCTION_MODE}
                openGraph={{
                    title: title,
                    description: description,
                    type: 'website',
                    locale: 'en_IE',
                    url,
                    site_name: title || globalConstants.appName,
                    images: [
                        {
                            url: fetched_form?.coverImage || workspace?.profileImage,
                            alt: title
                        }
                    ]
                }}
            />
            <div className={`absolute bottom-0 left-0 right-0 top-0 !m-0 !bg-white !p-0 ${showBranding ? '!mb-6' : ''}`}>
                {form?.settings?.provider === 'typeform' && <Widget id={form?.formId} style={{ height: '100vh' }} className="my-form" />}
                {form?.settings?.provider === 'self' && (
                    <div className="flex h-full w-full justify-center overflow-auto !bg-white pb-6">
                        <BetterCollectedForm form={form} enabled={!isFormDisabled} isCustomDomain={hasCustomDomain} />
                    </div>
                )}
            </div>
            {showBranding && <PoweredBy />}
        </Layout>
    );
}

export async function getServerSideProps(_context: any) {
    const slug = _context.params.id;
    let back = false;
    const query = _context.query;

    if (query?.back) {
        back = (query?.back && (query?.back === 'true' || query?.back === true)) ?? false;
    }

    const hasCustomDomain = checkHasCustomDomain(_context);

    if (!hasCustomDomain) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }
    let form = null;
    const config = getServerSideAuthHeaderConfig(_context);
    const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
    const { id } = _context.query;
    try {
        const formResponse = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/${globalProps.workspace?.id}/forms/${id}`, config);
        form = (await formResponse?.json().catch((e: any) => e)) ?? null;
        if (!form) {
            return {
                notFound: true
            };
        }
        return {
            props: {
                ...globalProps,
                slug,
                back,
                form
            }
        };
    } catch (err) {
        return {
            props: {
                ...globalProps,
                slug,
                back,
                error: true
            }
        };
    }
}

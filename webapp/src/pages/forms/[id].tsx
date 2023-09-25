import React, { useEffect, useRef } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { useRouter } from 'next/router';

import BetterCollectedForm from '@Components/Form/BetterCollectedForm';
import { ChevronLeft } from '@mui/icons-material';
import { Button } from '@mui/material';
import { Widget } from '@typeform/embed-react';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import PoweredBy from '@app/components/ui/powered-by';
import environments from '@app/configs/environments';
import globalConstants from '@app/constants/global';
import { localesCommon } from '@app/constants/locales/common';
import Layout from '@app/layouts/_layout';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { Plan } from '@app/models/dtos/UserStatus';
import { StandardFormDto } from '@app/models/dtos/form';
import { selectAuthStatus } from '@app/store/auth/selectors';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceFormQuery } from '@app/store/workspaces/api';
import { checkHasCustomDomain, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export default function SingleFormPage(props: any) {
    const { back, slug, hasCustomDomain, workspace, form: fetched_form, error: fetched_form_error } = props;

    const { data, isLoading, error } = useGetWorkspaceFormQuery({ workspace_id: workspace.id, custom_url: slug });

    const router = useRouter();
    const form: StandardFormDto | undefined = data;

    const social_preview = fetched_form_error ? form : fetched_form;

    const title = fetched_form?.title ?? workspace?.title;
    const description = fetched_form?.description?.slice(0, 100) ?? '';
    const url = globalConstants.socialPreview.url;

    const iframeRef = useRef(null);
    const { openModal } = useFullScreenModal();

    const responderUri = form?.settings?.embedUrl || '';
    const { t } = useTranslation();

    // @ts-ignore
    if (error && error?.status === 401) {
        return (
            <div className="min-h-screen min-w-screen  flex flex-col items-center justify-center">
                <span>You are trying to access a private form. Please login to continue.</span>
                <Button
                    onClick={() => {
                        openModal('LOGIN_VIEW');
                    }}
                >
                    Login
                </Button>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen min-w-screen text-center flex items-center justify-center">
                Error loading form!! <br />
                Either the form does not exist or you do not have access to this form.
            </div>
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
            pathName = `/${router.query.workspace_name}`;
        }

        router
            .push(
                {
                    pathname: pathName,
                    query: { view: 'forms' }
                },
                undefined,
                { scroll: true, shallow: true }
            )
            .then((r) => r)
            .catch((e) => e);
    };

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
                <div className="relative !bg-white !min-h-screen">
                    {back && (
                        <div className="flex cursor-pointer mt-5 items-center gap-2 px-5 lg:px-20 w-auto z-10 hover:!-translate-y-0 focus:-translate-y-0" onClick={() => goToForms()}>
                            <ChevronLeft height={24} width={24} />
                            <span className="sh1">{t(localesCommon.forms)}</span>
                        </div>
                    )}
                    <div className="absolute left-0 right-0 top-16 bottom-0 !p-0 w-full items-start justify-between rounded-lg bg-white">
                        <div className="flex flex-col items-center gap-8 justify-between p-10">
                            <div className="py-6 px-3 max-w-xs text-center">
                                <svg aria-hidden="true" className="mx-auto mb-4 text-yellow-500 w-14 h-14 dark:text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                </svg>
                                <h3 className="mb-5 text-lg font-bold text-gray-700 dark:text-gray-400">{form?.title}</h3>
                                <p className="mb-5 text-sm font-normal text-gray-500 dark:text-gray-400">{form?.description}</p>

                                <div className="px-4 py-10 mb-4 text-sm text-yellow-800 rounded-lg bg-yellow-50 dark:bg-gray-800 dark:text-yellow-300" role="alert">
                                    <span className="font-medium">Warning!</span> This form consists file upload. You may need to open it in a new tab to fill it out.
                                </div>
                                <ActiveLink
                                    href={responderUri}
                                    data-modal-hide="popup-modal"
                                    type="button"
                                    className="text-white bg-blue-500 hover:bg-blue-400 focus:ring-4 focus:outline-none focus:ring-red-300 dark:focus:ring-red-800 font-medium rounded-lg text-sm inline-flex items-center px-5 py-2.5 text-center mr-2"
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
                <div className="!min-h-screen relative">
                    <div className="absolute left-0 right-0 top-0 bottom-0 !p-0 !m-0'">
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

    return (
        <Layout showNavbar={false} isCustomDomain={hasCustomDomain} isClientDomain={!hasCustomDomain} showAuthAccount={true} className="relative !bg-white !min-h-screen">
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
            <div className={'absolute left-0 right-0 top-0 bottom-0 !bg-white !p-0 !m-0'}>
                {form?.settings?.provider === 'typeform' && <Widget id={form?.formId} style={{ height: '100vh' }} className="my-form" />}
                {form?.settings?.provider === 'self' && (
                    <div className="flex !bg-white justify-center overflow-auto h-full w-full pb-6">
                        <BetterCollectedForm form={form} enabled={true} isCustomDomain={hasCustomDomain} />
                    </div>
                )}
            </div>
            {(!workspace?.isPro || !form?.settings?.disableBranding) && <PoweredBy />}
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

    // return {
    //     props: {
    //         ...globalProps,
    //         slug,
    //         back
    //     }
    // };
}

import React, { useEffect } from 'react';

import { appWithTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { ThemeProvider } from 'next-themes';
import type { AppProps } from 'next/app';
import dynamic from 'next/dynamic';

import AuthStatusDispatcher from '@Components/HOCs/AuthStatusDispatcher';
import EnabledFormProviders from '@Components/HOCs/EnabledFormProviders';
import ServerSideWorkspaceDispatcher from '@Components/HOCs/ServerSideWorkspaceDispatcher';
import { CacheProvider, EmotionCache, css } from '@emotion/react';
import { GlobalStyles } from '@mui/material';
import CssBaseline from '@mui/material/CssBaseline';
import '@uiw/react-markdown-preview/dist/markdown.min.css';
import '@uiw/react-markdown-preview/esm/styles/markdown.css';
import '@uiw/react-md-editor/dist/mdeditor.min.css';
import 'katex/dist/katex.min.css';
import ReactGA from 'react-ga4';
import 'react-phone-input-2/lib/style.css';
import { Provider } from 'react-redux';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { PersistGate } from 'redux-persist/integration/react';
import 'swiper/css';
import 'swiper/css/navigation';
import 'vanilla-cookieconsent/dist/cookieconsent.css';

import '@app/assets/css/globals.css';
import CookieConsent from '@app/components/cookie/cookie-consent';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import NextNProgress from '@app/components/ui/nprogress';
import createEmotionCache from '@app/configs/createEmotionCache';
import environments from '@app/configs/environments';
import globalConstants from '@app/constants/global';
import MuiThemeProvider from '@app/layouts/_mui-theme-provider';
import { usePreserveScroll } from '@app/lib/hooks/use-preserve-scroll';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { persistor, store } from '@app/store/store';
import { NextPageWithLayout } from '@app/types';

const ModalContainer = dynamic(() => import('@app/components/modal-views/container'));
const FullScreenModalContainer = dynamic(() => import('@app/components/modal-views/full-screen-modal-container'));

// Client-side cache, shared for the whole session of the user in the browser.
const clientSideEmotionCache = createEmotionCache();

interface IWorkspacePageProps {
    workspace: WorkspaceDto | null;
}

type AppPropsWithLayout = AppProps & {
    Component: NextPageWithLayout;
    emotionCache?: EmotionCache;
    pageProps: IWorkspacePageProps | any;
};

function MainApp({ Component, pageProps, router, emotionCache = clientSideEmotionCache }: AppPropsWithLayout) {
    const getLayout = Component.getLayout ?? ((page: any) => page);

    //TODO: configure NextSEO component for all pages
    let title = globalConstants.title || globalConstants.socialPreview.title;
    let description = globalConstants.socialPreview.desc;
    let url = globalConstants.socialPreview.url;
    let imageUrl = globalConstants.socialPreview.image;

    const workspace: WorkspaceDto | null = pageProps?.workspace;
    title = workspace?.title ?? title;
    imageUrl = workspace?.profileImage ?? imageUrl;
    url = workspace?.customDomain ?? url;
    description = workspace?.description ?? description;

    usePreserveScroll();

    useEffect(() => {
        if (!!environments.GA_MEASUREMENT_ID) {
            ReactGA.initialize(environments.GA_MEASUREMENT_ID);
            ReactGA.send('pageview');
        }
    }, []);

    return (
        <ThemeProvider attribute="class" enableSystem={false} forcedTheme="light" defaultTheme="light">
            <CacheProvider value={emotionCache}>
                <MuiThemeProvider>
                    {/* CssBaseline kickstart an elegant, consistent, and simple baseline to build upon. */}
                    <CssBaseline />
                    <GlobalStyles
                        styles={css`
                            :root {
                                body {
                                    background-color: #f2f7ff;
                                    color: #121212;
                                }
                            }

                            [data-theme='dark'] {
                                body {
                                    background-color: #121212;
                                    color: #fff;
                                }
                            }
                        `}
                    />
                    <NextSeo
                        title={title || globalConstants.socialPreview.title}
                        description={description}
                        noindex={!environments.IS_IN_PRODUCTION_MODE}
                        nofollow={!environments.IS_IN_PRODUCTION_MODE}
                        openGraph={{
                            type: 'website',
                            locale: 'en_IE',
                            url,
                            site_name: title || globalConstants.appName,
                            description: description,
                            title,
                            images: [
                                {
                                    url: imageUrl,
                                    alt: title ?? 'Better Collected'
                                }
                            ]
                        }}
                        twitter={{
                            handle: globalConstants.twitterHandle,
                            site: url,
                            cardType: 'summary_large_image'
                        }}
                    />
                    <CookieConsent />
                    <NextNProgress color="#0764EB" startPosition={0} stopDelayMs={400} height={2} options={{ easing: 'ease' }} />
                    <ToastContainer position="bottom-center" autoClose={5000} hideProgressBar newestOnTop closeOnClick rtl={false} pauseOnFocusLoss={false} draggable pauseOnHover={false} theme="dark" />{' '}
                    <Provider store={store}>
                        <PersistGate loading={<FullScreenLoader />} persistor={persistor}>
                            <EnabledFormProviders>
                                <ServerSideWorkspaceDispatcher workspace={pageProps?.workspace}>
                                    <AuthStatusDispatcher workspace={pageProps?.workspace}>
                                        {getLayout(<Component {...pageProps} key={router.asPath} />)}
                                        {/*<ModalContainer />*/}
                                        <FullScreenModalContainer />
                                    </AuthStatusDispatcher>
                                </ServerSideWorkspaceDispatcher>
                            </EnabledFormProviders>
                        </PersistGate>
                    </Provider>
                </MuiThemeProvider>
            </CacheProvider>
        </ThemeProvider>
    );
}

export default appWithTranslation(MainApp);

import React, { useEffect } from 'react';

import { appWithTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { ThemeProvider } from 'next-themes';
import type { AppProps } from 'next/app';
import { useRouter } from 'next/router';

import { CacheProvider, EmotionCache, css } from '@emotion/react';
import { GlobalStyles } from '@mui/material';
import CssBaseline from '@mui/material/CssBaseline';
import CookieConsent from 'react-cookie-consent';
import ReactGA from 'react-ga4';
import { Provider } from 'react-redux';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { PersistGate } from 'redux-persist/integration/react';
import 'swiper/css';
import 'swiper/css/navigation';

import '@app/assets/css/globals.css';
import ModalContainer from '@app/components/modal-views/container';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import NextNProgress from '@app/components/ui/nprogress';
import createEmotionCache from '@app/configs/createEmotionCache';
import environments from '@app/configs/environments';
import globalConstants from '@app/constants/global';
import { consoleTextStyle, consoleWarningStyle } from '@app/constants/styles';
import MuiThemeProvider from '@app/layouts/_mui-theme-provider';
import { persistor, store } from '@app/store/store';
import { NextPageWithLayout } from '@app/types';

// Client-side cache, shared for the whole session of the user in the browser.
const clientSideEmotionCache = createEmotionCache();

type AppPropsWithLayout = AppProps & {
    Component: NextPageWithLayout;
    emotionCache?: EmotionCache;
    pageProps: any;
};

function MainApp({ Component, pageProps, emotionCache = clientSideEmotionCache }: AppPropsWithLayout) {
    // console.info(globalConstants.consoleWarningTitle, consoleWarningStyle);
    // console.info(globalConstants.consoleWarningDescription, consoleTextStyle);

    const router = useRouter();

    const getLayout = Component.getLayout ?? ((page: any) => page);

    //TODO: configure NextSEO component for all pages
    let title = globalConstants.title || globalConstants.socialPreview.title;
    let description = globalConstants.socialPreview.desc;
    let url = globalConstants.socialPreview.url;
    let imageUrl = globalConstants.socialPreview.image;

    const hasCustomDomain = !!pageProps?.hasCustomDomain;
    if (hasCustomDomain && !!pageProps?.companyJson) {
        title = pageProps?.companyJson?.companyTitle ?? title;
        imageUrl = pageProps?.companyJson?.companyProfile ?? imageUrl;
        url = pageProps?.companyJson?.companyDomain ?? url;
        description = pageProps?.companyJson?.companyDescription ?? description;
    }

    useEffect(() => {
        if (!!environments.GA_MEASUREMENT_ID) {
            ReactGA.initialize(environments.GA_MEASUREMENT_ID);
            ReactGA.send('pageview');
        }
    }, []);

    return (
        <ThemeProvider attribute="class" enableSystem={false} defaultTheme="light">
            <CacheProvider value={emotionCache}>
                <MuiThemeProvider>
                    {/* CssBaseline kickstart an elegant, consistent, and simple baseline to build upon. */}
                    <CssBaseline />
                    <GlobalStyles
                        styles={css`
                            :root {
                                body {
                                    background-color: #fff;
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
                                    alt: hasCustomDomain ? title : 'Better Collected'
                                }
                            ]
                        }}
                        twitter={{
                            handle: globalConstants.twitterHandle,
                            site: url,
                            cardType: 'summary_large_image'
                        }}
                    />
                    <CookieConsent
                        location="bottom"
                        buttonText="I understand"
                        cookieName="BetterCookie"
                        style={{ background: '#5492f7', display: 'flex', alignItems: 'center' }}
                        buttonStyle={{ color: '#4e503b', fontSize: '13px', borderRadius: '3px' }}
                        expires={150}
                    >
                        This website uses cookies to enhance the user experience.{' '}
                        <p className={'cursor-pointer mt-2 text-white hover:text-gray-300'} onClick={() => router.push('https://www.termsfeed.com/blog/cookies/')}>
                            What are cookies?
                        </p>
                    </CookieConsent>
                    <NextNProgress color="#f04444" startPosition={0} stopDelayMs={400} height={5} options={{ easing: 'ease' }} />
                    <ToastContainer theme="colored" position="bottom-right" autoClose={6000} hideProgressBar newestOnTop={false} closeOnClick rtl={false} pauseOnFocusLoss draggable pauseOnHover />
                    <Provider store={store}>
                        <PersistGate loading={<FullScreenLoader />} persistor={persistor}>
                            {getLayout(<Component {...pageProps} />)}
                            <ModalContainer />
                        </PersistGate>
                    </Provider>
                </MuiThemeProvider>
            </CacheProvider>
        </ThemeProvider>
    );
}

export default MainApp;
// export default appWithTranslation(MainApp);

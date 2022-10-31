import { appWithTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { ThemeProvider } from 'next-themes';
import type { AppProps } from 'next/app';
import { useRouter } from 'next/router';

import { CacheProvider, css } from '@emotion/react';
import { GlobalStyles, StyledEngineProvider } from '@mui/material';
import CookieConsent from 'react-cookie-consent';
import ReactGA from 'react-ga4';

import createEmotionCache from '@app/configs/createEmotionCache';
import environments from '@app/configs/environments';
import globalConstants from '@app/constants/global';
import MuiThemeProvider from '@app/layouts/_mui-theme-provider';

import '../../styles/globals.css';

// Client-side cache, shared for the whole session of the user in the browser.
const clientSideEmotionCache = createEmotionCache();

ReactGA.initialize(environments.GA_MEASUREMENT_ID);
ReactGA.send('pageview');

function MainApp({ Component, pageProps }: AppProps) {
    //TODO: configure NextSEO component for all pages
    let title = globalConstants.title || globalConstants.socialPreview.title;
    let description = globalConstants.socialPreview.desc;
    let url = globalConstants.socialPreview.url;
    let imageUrl = globalConstants.socialPreview.image;

    const router = useRouter();

    return (
        <StyledEngineProvider injectFirst>
            <CookieConsent location="bottom" buttonText="I understand" cookieName="BetterCookie" style={{ background: '#007AFF' }} buttonStyle={{ color: '#4e503b', fontSize: '13px', borderRadius: '3px' }} expires={150}>
                This website uses cookies to enhance the user experience.{' '}
                <p className={'cursor-pointer mt-2 text-white hover:text-gray-300'} onClick={() => router.push('https://www.termsfeed.com/blog/cookies/')}>
                    What are cookies?
                </p>
            </CookieConsent>
            <ThemeProvider attribute={'class'} enableSystem={false} defaultTheme={'light'}>
                <CacheProvider value={clientSideEmotionCache}>
                    <MuiThemeProvider>
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
                                site_name: globalConstants.appName,
                                description: description,
                                title,
                                images: [
                                    {
                                        url: imageUrl,
                                        alt: 'Better Collected'
                                    }
                                ]
                            }}
                            twitter={{
                                handle: globalConstants.twitterHandle,
                                site: url,
                                cardType: 'summary_large_image'
                            }}
                        />
                        <Component {...pageProps} />
                    </MuiThemeProvider>
                </CacheProvider>
            </ThemeProvider>
        </StyledEngineProvider>
    );
}

export default appWithTranslation(MainApp);

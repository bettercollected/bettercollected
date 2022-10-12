import type {AppProps} from 'next/app'
import createEmotionCache from "@app/configs/createEmotionCache";
import {ThemeProvider} from "next-themes";
import {CacheProvider} from '@emotion/react';
import MuiThemeProvider from "@app/layouts/_mui-theme-provider";
import {GlobalStyles, StyledEngineProvider} from "@mui/material";
import {globalStyles} from "@app/configs/muiTheme";
import { NextSeo } from 'next-seo';

import { appWithTranslation } from 'next-i18next';

// Client-side cache, shared for the whole session of the user in the browser.
const clientSideEmotionCache = createEmotionCache();

import globalConstants from "@app/constants/global";
import environments from "@app/configs/environments";

import "react-responsive-carousel/lib/styles/carousel.min.css"; // requires a loader
import '../../styles/globals.css'

function MyApp({Component, pageProps}: AppProps) {

    //TODO: configure NextSEO component for all pages
    let title = globalConstants.title || globalConstants.socialPreview.title;
    let description = globalConstants.socialPreview.desc;
    let url = globalConstants.socialPreview.url;
    let imageUrl = globalConstants.socialPreview.image;

    return (
        <StyledEngineProvider injectFirst>
        <ThemeProvider attribute={"class"} enableSystem={false} defaultTheme={"light"}>
            <CacheProvider value={clientSideEmotionCache}>
                <MuiThemeProvider>
                    <GlobalStyles
                        styles={globalStyles}
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
    )
}

export default appWithTranslation(MyApp)

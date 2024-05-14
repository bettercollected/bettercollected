'use client';

import { ThemeProvider as NextThemeProvider } from 'next-themes';

import { CacheProvider, css, EmotionCache } from '@emotion/react';
import { CssBaseline, GlobalStyles } from '@mui/material';

import createEmotionCache from '@app/configs/createEmotionCache';
import MuiThemeProvider from '@app/layouts/_muiThemeProvider';
import React from 'react';
import { AppProgressBar as ProgressBar } from 'next-nprogress-bar';

const clientSideEmotionCache = createEmotionCache();

export default function ThemeProvider({
    children,
    emotionCache = clientSideEmotionCache
}: Readonly<{
    children: React.ReactNode | React.ReactNode[];
    emotionCache?: EmotionCache;
}>) {
    return (
        <NextThemeProvider attribute="class" enableSystem={true} forcedTheme="light" defaultTheme="light">
            <CacheProvider value={emotionCache}>
                <MuiThemeProvider>
                    {/* CssBaseline kickstart an elegant, consistent, and simple baseline to build upon. */}
                    <CssBaseline />
                    <GlobalStyles
                        styles={css`
                            :root {
                                body {
                                    background: #f2f7ff;
                                    background-color: #f2f7ff;
                                    color: #121212;
                                }
                            }

                            [data-theme='dark'] {
                                body {
                                    background: #121212;
                                    background-color: #121212;
                                    color: #fff;
                                }
                            }
                        `}
                    />
                    {children}
                    <ProgressBar height="4px" color="#0764EB" options={{ showSpinner: false }} shallowRouting />
                </MuiThemeProvider>
            </CacheProvider>
        </NextThemeProvider>
    );
}

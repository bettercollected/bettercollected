'use client';

import { ThemeProvider as NextThemeProvider } from 'next-themes';

import { CacheProvider, EmotionCache, css } from '@emotion/react';
import { CssBaseline, GlobalStyles } from '@mui/material';

import createEmotionCache from '@app/configs/createEmotionCache';
import MuiThemeProvider from '@app/layouts/_muiThemeProvider';

const clientSideEmotionCache = createEmotionCache();

export default function ThemeProvider({
    children,
    emotionCache = clientSideEmotionCache
}: Readonly<{
    children: React.ReactNode | React.ReactNode[];
    emotionCache?: EmotionCache;
}>) {
    return (
        <NextThemeProvider
            attribute="class"
            enableSystem={true}
            forcedTheme="light"
            defaultTheme="light"
        >
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
                </MuiThemeProvider>
            </CacheProvider>
        </NextThemeProvider>
    );
}

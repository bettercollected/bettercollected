import React from 'react';

import type { Metadata } from 'next';
import { Public_Sans } from 'next/font/google';

import '@app/assets/css/globals.css';
import SwRegister from '@app/components/common/sw-register';
import environments from '@app/configs/environments';
import { DialogModalContainer } from '@app/lib/hooks/use-dialog-modal';
import { SecondaryDialogModalContainer } from '@app/lib/hooks/use-secondary-dialog-modal';
import { Toaster } from '@app/shadcn/components/ui/toaster';
import { cn } from '@app/shadcn/util/lib';
import AuthProvider from '@app/shared/hocs/auth-provider';
import I18nProvider from '@app/shared/hocs/i18n-provider';
import ReduxProvider from '@app/shared/hocs/redux-provider';
import ThemeProvider from '@app/shared/hocs/theme-provider';
import BaseModalContainer from '@Components/modals/containers/base-modal-container';
import { Viewport } from 'next';

// One honest, humanist face used everywhere (see Design-Language.md §2).
// Public Sans is self-hosted by next/font — no external font request at runtime.
const publicSans = Public_Sans({ subsets: ['latin'], display: 'swap', variable: '--font-public-sans' });

export const viewport: Viewport = {
    themeColor: '#ffffff',
    width: 'device-width',
    initialScale: 1
};

export const metadata: Metadata = {
    metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || 'https://bettercollected.com'),
    title: {
        default: 'BetterCollected',
        template: '%s | BetterCollected'
    },
    description: 'Bettercollected formBuilder - Build forms simply and quickly.',
    keywords: ['Form Builder', 'Survey', 'Data Collection', 'BetterCollected'],
    authors: [{ name: 'BetterCollected Team' }],
    creator: 'BetterCollected',
    publisher: 'BetterCollected',
    openGraph: {
        type: 'website',
        locale: 'en_US',
        url: 'https://bettercollected.com',
        title: 'BetterCollected',
        description: 'Bettercollected formBuilder - Build forms simply and quickly.',
        siteName: 'BetterCollected',
        images: [
            {
                url: '/images/image.png',
                width: 1200,
                height: 630,
                alt: 'BetterCollected'
            }
        ]
    },
    twitter: {
        card: 'summary_large_image',
        title: 'BetterCollected',
        description: 'Bettercollected formBuilder - Build forms simply and quickly.',
        images: ['/images/image.png'],
        creator: '@bettercollected'
    },
    icons: {
        icon: '/favicon.ico'
    },
    manifest: '/site.webmanifest'
};

export default function RootLayout({
    children
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en" suppressHydrationWarning>
            <body className={cn('max-h-screen overflow-auto', publicSans.variable, publicSans.className)}>
                {environments.UMAMI_SCRIPT_URL && environments.UMAMI_WEBSITE_ID && (
                    // Plain <script> like /api/config below, NOT next/script: next/script
                    // only injects after hydration completes, so any client-side stall
                    // (or a lazyOnload idle wait) silently drops the tracker. A plain
                    // deferred tag executes with the document, independent of app health.
                    // data-auto-track="false": Umami's automatic pageview would fire with
                    // the raw URL alongside our explicit canonical-path event (see
                    // src/lib/analytics/umami.ts), double-counting every public form view
                    // and splitting the same form across client-host/custom-domain paths.
                    // Only the explicit canonical event is sent — which also means
                    // logged-in dashboard activity is never tracked, only public forms.
                    <script src={environments.UMAMI_SCRIPT_URL} data-website-id={environments.UMAMI_WEBSITE_ID} data-auto-track="false" defer></script>
                )}
                <SwRegister />
                <script src="/api/config" defer></script>
                <ThemeProvider>
                    <I18nProvider>
                        <Toaster />
                        <ReduxProvider>
                            <AuthProvider>
                                {children}
                                <DialogModalContainer />
                                <SecondaryDialogModalContainer />
                                <BaseModalContainer />
                            </AuthProvider>
                        </ReduxProvider>
                    </I18nProvider>
                </ThemeProvider>
            </body>
        </html>
    );
}
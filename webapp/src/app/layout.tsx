import React from 'react';

import type { Metadata } from 'next';
import { Inter } from 'next/font/google';

import '@app/assets/css/globals.css';
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
import Head from 'next/head';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
    title: 'BetterCollected',
    description: 'Bettercollected formBuilder'
};

export default function RootLayout({
    children
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html>
            <Head>
                {environments.NEXT_PUBLIC_NODE_ENV === 'production' && environments.UMAMI_WEBSITE_ID && <script defer src="https://umami.sireto.io/script.js" data-website-id={environments.UMAMI_WEBSITE_ID}></script>}
            </Head>
            <body className={cn('max-h-screen overflow-auto', inter.className)}>
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
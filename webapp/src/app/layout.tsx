import React from 'react';

import type { Metadata } from 'next';
import { Inter } from 'next/font/google';

import '@app/assets/css/globals.css';
import environments from '@app/configs/environments';
import { DialogModalContainer } from '@app/lib/hooks/useDialogModal';
import { SecondaryDialogModalContainer } from '@app/lib/hooks/useSecondaryDialogModal';
import { Toaster } from '@app/shadcn/components/ui/toaster';
import { cn } from '@app/shadcn/util/lib';
import AuthProvider from '@app/shared/hocs/AuthProvider';
import I18nProvider from '@app/shared/hocs/I18nProvider';
import ReduxProvider from '@app/shared/hocs/ReduxProvider';
import ThemeProvider from '@app/shared/hocs/ThemeProvider';
import BaseModalContainer from '@Components/Modals/Containers/BaseModalContainer';

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
            <head>
                {environments.NEXT_PUBLIC_NODE_ENV === 'production' && environments.UMAMI_WEBSITE_ID && <script defer src="https://umami.sireto.io/script.js" data-website-id={environments.UMAMI_WEBSITE_ID}></script>}
                <script src="/api/config" defer></script>
            </head>
            <body className={cn('max-h-screen overflow-auto', inter.className)}>
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
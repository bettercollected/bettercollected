import React from 'react';

import type { Metadata } from 'next';
import { Inter } from 'next/font/google';

import 'nprogress/nprogress.css';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import 'swiper/css';
import 'swiper/css/navigation';
import 'vanilla-cookieconsent/dist/cookieconsent.css';

import BaseModalContainer from '@Components/Modals/Containers/BaseModalContainer';
import '@app/assets/css/globals.css';
import { DialogModalContainer } from '@app/lib/hooks/useDialogModal';
import { Toaster } from '@app/shadcn/components/ui/toaster';
import { cn } from '@app/shadcn/util/lib';
import AuthProvider from '@app/shared/hocs/AuthProvider';
import ReduxProvider from '@app/shared/hocs/ReduxProvider';
import ThemeProvider from '@app/shared/hocs/ThemeProvider';
import environments from '@app/configs/environments';
import SetClarityUserId from '@app/utils/clarityUtils';
import { SecondaryDialogModalContainer } from '@app/lib/hooks/useSecondaryDialogModal';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
    title: 'BetterCollected',
    description: 'Bettercollected V2 formBuilder'
};

export default function RootLayout({
    children
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en">
            <head>
                <script defer src="/script.js" data-website-id={environments.UMAMI_WEBSITE_ID}></script>
                <script src="/api/config" defer></script>
                {embedMicrosoftClarityScript()}
            </head>
            <body className={cn('max-h-screen overflow-hidden', inter.className)}>
                <ThemeProvider>
                    <ToastContainer position="bottom-center" autoClose={5000} hideProgressBar newestOnTop closeOnClick rtl={false} pauseOnFocusLoss={false} draggable pauseOnHover={false} theme="dark" />
                    <Toaster />
                    <AuthProvider>
                        <ReduxProvider>
                            {children}
                            <DialogModalContainer />
                            <SecondaryDialogModalContainer />
                            <BaseModalContainer />
                            <SetClarityUserId />
                        </ReduxProvider>
                    </AuthProvider>
                </ThemeProvider>
            </body>
        </html>
    );
}

function embedMicrosoftClarityScript() {
    if (environments.MICROSOFT_CLARITY_TRACKING_CODE)
        return (
            <script
                type="text/javascript"
                dangerouslySetInnerHTML={{
                    __html: `
                (function(c,l,a,r,i,t,y){
                    c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
                    t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
                    y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
                })(window, document, "clarity", "script", "${environments.MICROSOFT_CLARITY_TRACKING_CODE}");
            `
                }}
            />
        );
    return <></>;
}

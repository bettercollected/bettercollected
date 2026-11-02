'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';

import { Globe, ShieldCheck, Trash2 } from 'lucide-react';

import SiretoFooter from '@app/components/layout/sireto-footer';
import { useMfaT } from '@app/components/mfa/use-mfa-t';
import Logo from '@app/components/ui/logo';
import { localesCommon } from '@app/constants/locales/common';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { signUpScreen } from '@app/constants/locales/signup-screen';
import TopNavLayout from '@app/layouts/top-navbar-layout';
import { navigateTo } from '@app/utils/browser-navigation';
import { safeNextPath } from '@app/utils/mfa';

import MfaCodeForm from '@app/components/mfa/mfa-code-form';
import OtpCodeForm from './otp-code-form';
import OtpEmailForm from './otp-email-form';

/**
 * The sign-in screen is the first trust decision anyone makes about the
 * product, so the pitch panel practices what the product preaches: a calm
 * ink surface stating what bettercollected is and the rights it gives
 * responders — instead of the old marketing collage (gradient background,
 * outdated UI screenshots, and a sentence that ended mid-thought).
 */
export default function LoginView() {
    const { t } = useTranslation();
    const searchParams = useSearchParams();
    const isSignup = searchParams?.get('isSignup') === 'true';
    // Responders land here from a portal's "Verify email" — pitching the form
    // builder at them would be talking to the wrong person.
    const isResponder = searchParams?.get('type') === 'responder';
    const [email, setEmail] = useState('');
    const router = useRouter();
    const { t: tMfa, language: mfaLanguage } = useMfaT();
    // Google (or another provider) passed the first step and the server sent the browser back here for the second
    const arrivedForSecondFactor = searchParams?.get('mfa') === '1';
    const [secondFactorAfterEmail, setSecondFactorAfterEmail] = useState(false);
    const secondFactor = arrivedForSecondFactor || secondFactorAfterEmail;

    const creatorBullets = [
        { icon: ShieldCheck, text: 'A trust footer on every form — who is collecting, why, and the rights responders keep' },
        { icon: Globe, text: 'Every workspace gets its own branded site, with custom domains on Pro' },
        { icon: Trash2, text: 'Responders can view or delete their responses at any time' }
    ];

    const signInPanel = isResponder
        ? {
              title: 'See your submissions',
              description: "Verify your email to see every response you've submitted to this workspace — and request deletion of any of them.",
              bullets: undefined
          }
        : email
          ? {
                title: t(isSignup ? signUpScreen.features.otp_title : signInScreen.features.otp_title),
                description: t(isSignup ? signUpScreen.features.otp_description : signInScreen.features.otp_description),
                bullets: undefined
            }
          : {
                title: t(isSignup ? signUpScreen.features.title : signInScreen.features.title),
                description: t(isSignup ? signUpScreen.features.description : signInScreen.features.description),
                bullets: creatorBullets
            };

    const panel = secondFactor ? { title: tMfa('STAFF.MFA.SIGNIN.PANEL_TITLE'), description: tMfa('STAFF.MFA.SIGNIN.PANEL_DESCRIPTION'), bullets: undefined } : signInPanel;

    // after the second step: the page the sign-in came from (a path of this site), else the sign-in page, which sends a signed-in person on
    const finishSignIn = () => {
        navigateTo(safeNextPath(searchParams?.get('next')) ?? '/login');
    };

    return (
        <TopNavLayout className="min-h-screen mt-0! p-0!">
            <div className="flex h-full w-full flex-col lg:flex-row">
                <div className="order-2 flex w-full flex-col justify-center gap-8 bg-[#101828] px-8 py-14 lg:order-1 lg:min-h-screen lg:w-1/2 lg:px-16">
                    <h1 className="tracking-title max-w-[480px] text-[26px] font-semibold leading-snug text-white lg:text-[32px]">{panel.title}</h1>
                    <p className="max-w-[440px] text-[15px] leading-relaxed text-[#A8B3C4]">{panel.description}</p>
                    {panel.bullets && (
                        <ul className="flex max-w-[460px] flex-col gap-5">
                            {panel.bullets.map(({ icon: Icon, text }) => (
                                <li key={text} className="flex items-start gap-3 text-[15px] leading-relaxed text-[#DFE5EE]">
                                    <Icon className="mt-0.5 h-5 w-5 shrink-0 text-[#A8C0EA]" strokeWidth={1.8} aria-hidden="true" />
                                    {text}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
                <div className="relative order-1 flex min-h-fit w-full flex-col items-start justify-between px-8 py-7 sm:min-h-screen lg:order-2 lg:max-w-[50%] lg:py-8 xl:pl-[90px] xl:pr-28">
                    <div className="mb-20 lg:mb-0">
                        <Logo isLink={false} />
                        <h1 className="body4 text-black-800! mt-2">{t(signUpScreen.logoDescription)}</h1>
                    </div>

                    <div className="w-full">
                        {arrivedForSecondFactor ? (
                            <MfaCodeForm onSignedIn={finishSignIn} onBack={() => router.replace('/login')} />
                        ) : !email ? (
                            <OtpEmailForm setEmail={setEmail} isSignup={isSignup} />
                        ) : (
                            <OtpCodeForm email={email} setEmail={setEmail} onMfaChange={setSecondFactorAfterEmail} />
                        )}
                    </div>

                    <div className="mt-24 flex w-full flex-col gap-4 lg:mt-0">
                        <TermsAndCondition isSignup={isSignup} translate={secondFactor ? tMfa : undefined} language={secondFactor ? mfaLanguage : undefined} />
                        <SiretoFooter className="text-left" language={secondFactor ? mfaLanguage : undefined} />
                    </div>
                </div>
            </div>
        </TopNavLayout>
    );
}

// `translate`/`language`: the second step of a sign-in follows the person's language (Dutch for a Dutch browser), the rest of the page stays English
const TermsAndCondition = ({ isSignup, translate, language }: { isSignup: boolean; translate?: TFunction; language?: string }) => {
    const { t: pageT } = useTranslation();
    const t = translate ?? pageT;
    return (
        <div className="body4" lang={language}>
            {t(isSignup ? signUpScreen.signUpAgreementDescription : signInScreen.signinAgreementDescription)}
            <a href="https://bettercollected.com/terms-of-service" target="_blank" rel="noreferrer" className="mx-1 cursor-pointer underline text-brand-500 hover:text-brand-600">
                {t(localesCommon.termsOfServices.title)}
            </a>
            {t(localesCommon.and)}
            <a href="https://bettercollected.com/privacy-policy" target="_blank" rel="noreferrer" className="mx-1 cursor-pointer underline text-brand-500 hover:text-brand-600">
                {t(localesCommon.privacyPolicy.title)}
            </a>
            .
        </div>
    );
};

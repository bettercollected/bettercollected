'use client';

import { useState } from 'react';

import { useRouter, useSearchParams } from 'next/navigation';

import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';

import SiretoFooter from '@app/components/layout/sireto-footer';
import MfaCodeForm from '@app/components/mfa/mfa-code-form';
import { useMfaT } from '@app/components/mfa/use-mfa-t';
import DaybreakArt from '@app/components/ui/daybreak-art';
import Logo from '@app/components/ui/logo';
import { localesCommon } from '@app/constants/locales/common';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { signUpScreen } from '@app/constants/locales/signup-screen';
import TopNavLayout from '@app/layouts/top-navbar-layout';
import { navigateTo } from '@app/utils/browser-navigation';
import { safeNextPath } from '@app/utils/mfa';

import OtpCodeForm from './otp-code-form';
import OtpEmailForm from './otp-email-form';

/**
 * The sign-in screen is the first trust decision anyone makes about the
 * product. A creator gets one calm card on the app's canvas: the motif once,
 * the page's one heading, the form, and nothing that claims anything. A
 * responder (`?type=responder`, a portal's "Verify email") keeps the pitch
 * panel and paper mist: that page belongs to a workspace's responders, not to the app.
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

    const responderPanel = {
        title: 'See your submissions',
        description: "Verify your email to see every response you've submitted to this workspace — and request deletion of any of them."
    };

    const panel = secondFactor ? { title: tMfa('STAFF.MFA.SIGNIN.PANEL_TITLE'), description: tMfa('STAFF.MFA.SIGNIN.PANEL_DESCRIPTION') } : responderPanel;

    // after the second step: the page the sign-in came from (a path of this site), else the sign-in page, which sends a signed-in person on
    const finishSignIn = () => {
        navigateTo(safeNextPath(searchParams?.get('next')) ?? '/login');
    };

    // what the creator's card says: the page's one heading, and a line under it on the first step
    const title = secondFactor ? tMfa('STAFF.MFA.SIGNIN.PANEL_TITLE') : email ? t(signInScreen.checkEmail) : t(isSignup ? signUpScreen.signUp : signInScreen.welcomeBack);
    const intro = secondFactor || email ? undefined : t(isSignup ? signUpScreen.signUpToContinue : signInScreen.signInToContinue);

    const creatorPage = (
        <TopNavLayout className="mt-0! min-h-screen p-0!">
            <div className="flex min-h-screen w-full flex-col items-center gap-8 py-8 sm:py-12">
                <header className="flex flex-col items-center gap-1.5 text-center">
                    <Logo isLink={false} />
                    <p className="m-0 text-sm text-copy">{t(signUpScreen.logoDescription)}</p>
                </header>

                <div className="flex w-full flex-1 items-center justify-center">
                    <section aria-labelledby="signin-title" className="w-full max-w-[440px] overflow-hidden rounded border border-hairline-strong bg-surface">
                        <div className="h-[88px] bg-brand-tint sm:h-[104px]">
                            <DaybreakArt />
                        </div>
                        <div className="flex flex-col gap-6 p-6 sm:p-8">
                            <div className="flex flex-col gap-1.5" lang={secondFactor ? mfaLanguage : undefined}>
                                <h1 id="signin-title" className="m-0 text-2xl leading-snug font-semibold tracking-title-sm text-ink">
                                    {title}
                                </h1>
                                {intro && <p className="m-0 text-sm leading-relaxed text-copy">{intro}</p>}
                            </div>
                            {arrivedForSecondFactor ? (
                                <MfaCodeForm onSignedIn={finishSignIn} onBack={() => router.replace('/login')} />
                            ) : !email ? (
                                <OtpEmailForm setEmail={setEmail} isSignup={isSignup} card />
                            ) : (
                                <OtpCodeForm email={email} setEmail={setEmail} onMfaChange={setSecondFactorAfterEmail} card />
                            )}
                        </div>
                    </section>
                </div>

                <div className="flex w-full max-w-[440px] flex-col gap-3 text-center">
                    <TermsAndCondition isSignup={isSignup} translate={secondFactor ? tMfa : undefined} language={secondFactor ? mfaLanguage : undefined} />
                    <SiretoFooter className="text-center" language={secondFactor ? mfaLanguage : undefined} />
                </div>
            </div>
        </TopNavLayout>
    );

    const responderPage = (
        <TopNavLayout className="mt-0! min-h-screen p-0!">
            <div className="flex h-full w-full flex-col lg:flex-row">
                <div className="order-2 flex w-full flex-col justify-center gap-8 bg-[#101828] px-8 py-14 lg:order-1 lg:min-h-screen lg:w-1/2 lg:px-16">
                    <h1 className="max-w-[480px] text-[26px] leading-snug font-semibold tracking-title text-white lg:text-[32px]">{panel.title}</h1>
                    <p className="max-w-[440px] text-[15px] leading-relaxed text-[#A8B3C4]">{panel.description}</p>
                </div>
                <div className="relative order-1 flex min-h-fit w-full flex-col items-start justify-between px-8 py-7 sm:min-h-screen lg:order-2 lg:max-w-[50%] lg:py-8 xl:pr-28 xl:pl-[90px]">
                    <div className="mb-20 lg:mb-0">
                        <Logo isLink={false} />
                        <h1 className="body4 mt-2 text-black-800!">{t(signUpScreen.logoDescription)}</h1>
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

    return (
        // The creator's sign-in wears the app theme. The respondent's (`?type=responder`, also served on custom
        // domains) is a respondent route: no attribute, so it keeps paper mist and the pitch panel.
        <div data-app-theme={isResponder ? undefined : 'daybreak'}>{isResponder ? responderPage : creatorPage}</div>
    );
}

// `translate`/`language`: the second step of a sign-in follows the person's language (Dutch for a Dutch browser), the rest of the page stays English
const TermsAndCondition = ({ isSignup, translate, language }: { isSignup: boolean; translate?: TFunction; language?: string }) => {
    const { t: pageT } = useTranslation();
    const t = translate ?? pageT;
    return (
        <div className="body4" lang={language}>
            {t(isSignup ? signUpScreen.signUpAgreementDescription : signInScreen.signinAgreementDescription)}
            <a href="https://bettercollected.com/terms-of-service" target="_blank" rel="noreferrer" className="mx-1 cursor-pointer text-brand-500 underline hover:text-brand-600">
                {t(localesCommon.termsOfServices.title)}
            </a>
            {t(localesCommon.and)}
            <a href="https://bettercollected.com/privacy-policy" target="_blank" rel="noreferrer" className="mx-1 cursor-pointer text-brand-500 underline hover:text-brand-600">
                {t(localesCommon.privacyPolicy.title)}
            </a>
            .
        </div>
    );
};

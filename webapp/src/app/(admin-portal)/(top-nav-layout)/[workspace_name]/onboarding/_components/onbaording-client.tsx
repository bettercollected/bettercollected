'use client';

import { useState } from 'react';

import { Button } from '@app/shadcn/components/ui/button';
import { useTranslation } from 'react-i18next';

import EmptyState from '@app/components/ui/empty-state';
import Logo from '@app/components/ui/logo';
import { localesCommon } from '@app/constants/locales/common';
import { onBoarding } from '@app/constants/locales/onboarding-screen';
import OnboardingContainer from '@app/containers/onboarding';
import { UserStatus } from '@app/models/dtos/user-status';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

interface onBoardingProps {
    workspace?: WorkspaceDto;
    createWorkspace?: boolean;
}

export default function OnboardingClient({ workspace, createWorkspace }: onBoardingProps) {
    const { t } = useTranslation();
    const authStatus = useAppSelector(selectAuth);
    const user: UserStatus = !!authStatus ? authStatus : null;
    const [stepCount, setStepCount] = useState(createWorkspace ? 1 : 0);

    const increaseStep = () => {
        setStepCount(stepCount + 1);
    };

    // The first thing a new creator sees after the code: the empty states' card (the motif, one sentence, one next step)
    const StepZeroContent = (
        <>
            <div className="mt-[60px] flex flex-col items-center justify-center gap-2">
                <Logo isLink={false} />
                <p className="text-copy text-xs">{t(onBoarding.privacyFriendly)}</p>
            </div>
            <div className="mt-12 flex w-full justify-center px-4 sm:mt-16">
                <EmptyState
                    headingLevel={1}
                    className="max-w-[480px]"
                    title={`${t(localesCommon.hey)} ${user?.firstName || user?.email}!`}
                    description={t(onBoarding.welcomeMessage)}
                    action={
                        <Button size="medium" onClick={increaseStep}>
                            {t(onBoarding.addYourOrganization)}
                        </Button>
                    }
                />
            </div>
        </>
    );

    const StepOneContent = <OnboardingContainer workspace={workspace} createWorkspace={createWorkspace} />;

    return (
        <div className="flex h-screen w-full flex-col items-center overflow-auto bg-canvas pb-20">
            {stepCount === 0 && StepZeroContent}
            {stepCount === 1 && StepOneContent}
        </div>
    );
}

import React, { useState } from 'react';

import { GetServerSidePropsContext } from 'next';
import { useTranslation } from 'next-i18next';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import Logo from '@app/components/ui/logo';
import { localesCommon } from '@app/constants/locales/common';
import { onBoarding } from '@app/constants/locales/onboarding-screen';
import OnboardingContainer from '@app/containers/Onboarding';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { UserStatus } from '@app/models/dtos/UserStatus';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

interface onBoardingProps {
    workspace?: WorkspaceDto;
    createWorkspace?: boolean;
}

export async function getServerSideProps(_context: GetServerSidePropsContext) {
    const authUserProps = (await getAuthUserPropsWithWorkspace(_context)).props;
    if (!authUserProps) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }
    if (authUserProps && authUserProps?.workspace?.title && authUserProps?.workspace?.title.toLowerCase() !== 'untitled') {
        return {
            redirect: {
                permanent: false,
                destination: `/${authUserProps.workspace.workspaceName}/dashboard`
            }
        };
    }
    return {
        props: { ...authUserProps }
    };
}

export default function Onboarding({ workspace, createWorkspace }: onBoardingProps) {
    const { t } = useTranslation();
    const authStatus = useAppSelector(selectAuth);
    const user: UserStatus = !!authStatus ? authStatus : null;
    const [stepCount, setStepCount] = useState(createWorkspace ? 1 : 0);

    const increaseStep = () => {
        setStepCount(stepCount + 1);
    };

    const StepZeroContent = (
        <>
            <div className="mt-[60px] flex flex-col items-center justify-center gap-2">
                <Logo isLink={false} />
                <p className="text-black-800 text-xs">{t(onBoarding.privacyFriendly)}</p>
            </div>
            <div className="mt-[136px] flex h-full w-full flex-col items-center">
                <AuthAccountProfileImage image={user?.profileImage} name={user?.firstName || user?.lastName || user?.email} size={100} typography="!text-6xl" />
                <p className="text-black-900 pt-10 text-center text-2xl font-semibold">
                    {t(localesCommon.hey)} {user?.firstName || user?.email}!
                </p>
                <p className="text-black-800 pt-2 text-base">{t(onBoarding.welcomeMessage)}</p>
                <AppButton className="bg-new-blue-500 hover:bg-brand-600 mt-12 !py-3 px-8" size={ButtonSize.Medium} onClick={increaseStep}>
                    {t(onBoarding.addYourOrganization)}
                </AppButton>
            </div>
        </>
    );
    const StepOneContent = <OnboardingContainer workspace={workspace} createWorkspace={createWorkspace} />;

    return (
        <div className="flex h-screen w-full flex-col items-center overflow-auto bg-white pb-20">
            {stepCount === 0 && StepZeroContent}
            {stepCount === 1 && StepOneContent}
        </div>
    );
}

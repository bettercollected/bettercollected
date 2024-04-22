import React from 'react';

import { useTranslation } from 'next-i18next';

import ActiveLink from '@app/components/ui/links/active-link';
import PoweredBy from '@app/components/ui/powered-by';
import { localesCommon } from '@app/constants/locales/common';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface FooterProps {
    workspace: WorkspaceDto;
    isCustomDomain: boolean;
    showProTag?: boolean;
}

export default function WorkspaceFooter({ workspace, isCustomDomain, showProTag = true }: FooterProps) {
    const { t } = useTranslation();
    return (
        <div className="flex min-h-[44px] w-full flex-col justify-start gap-10 px-5 pb-6 md:flex-row md:items-center md:justify-between lg:px-10 xl:px-20">
            <div className="flex flex-col items-start justify-center gap-6 sm:flex-row sm:items-center sm:justify-between sm:gap-10">
                <ActiveLink target="_blank" className="body3 !text-black-800 hover:!text-brand-500 !not-italic !leading-none" href={workspace.termsOfService ?? `https://bettercollected.com/terms-of-service/`}>
                    {t(localesCommon.termsOfServices.title)}
                </ActiveLink>
                <ActiveLink target="_blank" className="body3 !text-black-800 hover:!text-brand-500 !not-italic !leading-none" href={workspace.privacyPolicy ?? `https://bettercollected.com/privacy-policy/`}>
                    {t(localesCommon.privacyPolicy.title)}
                </ActiveLink>
            </div>
            {!workspace?.isPro && <PoweredBy />}
        </div>
    );
}

import React from 'react';

import ActiveLink from '@app/components/ui/links/active-link';
import Logo from '@app/components/ui/logo';
import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface FooterProps {
    workspace: WorkspaceDto;
    isCustomDomain: boolean;
    showProTag?: boolean;
}

export default function WorkspaceFooter({ workspace, isCustomDomain, showProTag = true }: FooterProps) {
    return (
        <div className="w-full flex flex-col pb-6 px-5 lg:px-10 xl:px-20 min-h-[44px] justify-start md:flex-row md:justify-between md:items-center gap-10">
            <div className="flex flex-col gap-6 justify-center items-start sm:flex-row sm:gap-10 sm:justify-between sm:items-center">
                <ActiveLink target="_blank" className="body3 !not-italic !text-black-800 hover:!text-brand-500" href={workspace.terms_of_service_url ?? `https://bettercollected.com/terms-of-service/`}>
                    Terms of service
                </ActiveLink>
                <ActiveLink target="_blank" className="body3 !not-italic !text-black-800 hover:!text-brand-500" href={workspace.privacy_policy_url ?? `https://bettercollected.com/privacy-policy/`}>
                    Privacy Policy
                </ActiveLink>
            </div>
            {isCustomDomain && (
                <div data-testid="logo">
                    <p className="body3 !not-italic !text-black-800">Powered by</p>
                    <Logo showProTag={showProTag} />
                </div>
            )}
        </div>
    );
}

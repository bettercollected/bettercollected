import React from 'react';

import ActiveLink from '@app/components/ui/links/active-link';
import Logo from '@app/components/ui/logo';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface FooterProps {
    workspace: WorkspaceDto;
    isCustomDomain: boolean;
}

export default function WorkspaceFooter({ workspace, isCustomDomain }: FooterProps) {
    return (
        <div className="absolute left-0 bottom-0 w-full flex flex-col justify-start md:flex-row md:justify-between md:items-center px-6 sm:px-8 lg:px-12 py-2 border-t-[1.5px] border-[#eaeaea] bg-transparent drop-shadow-main mb-0">
            <div className="flex justify-between mb-4">
                <ActiveLink target={'_blank'} className="mt-6 md:mt-0 text-sm md:text-lg mr-6 hover:text-gray-600" href={workspace.terms_of_service_url ?? ''}>
                    Terms of service
                </ActiveLink>
                <ActiveLink target={'_blank'} className="mt-6 md:mt-0 text-sm md:text-lg hover:text-gray-600" href={workspace.privacy_policy_url ?? ''}>
                    Privacy Policy
                </ActiveLink>
            </div>
            {isCustomDomain && (
                <div className="mb-2">
                    <p>Powered by</p>
                    <Logo className="!text-lg" />
                </div>
            )}
        </div>
    );
}

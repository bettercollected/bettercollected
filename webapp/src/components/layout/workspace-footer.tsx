import React from 'react';

import ActiveLink from '@app/components/ui/links/active-link';
import Logo from '@app/components/ui/logo';
import environments from '@app/configs/environments';
import DynamicContainer from '@app/containers/DynamicContainer';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface FooterProps {
    workspace: WorkspaceDto;
    isCustomDomain: boolean;
}

export default function WorkspaceFooter({ workspace, isCustomDomain }: FooterProps) {
    return (
        <div className="w-full flex justify-center">
            <DynamicContainer>
                <div className=" w-full flex flex-col justify-start md:flex-row md:justify-between md:items-center border-t-[1.5px] border-[#eaeaea] bg-transparent drop-shadow-main pt-3 mb-0">
                    <div className="flex justify-between mb-4">
                        <ActiveLink target={'_blank'} className="mt-6 md:mt-0 text-sm md:text-lg mr-6 hover:text-gray-600" href={workspace.terms_of_service_url ?? `https://${environments.CLIENT_DOMAIN}/legal/terms-and-conditions-2022.pdf`}>
                            Terms of service
                        </ActiveLink>
                        <ActiveLink target={'_blank'} className="mt-6 md:mt-0 text-sm md:text-lg hover:text-gray-600" href={workspace.privacy_policy_url ?? `https://${environments.CLIENT_DOMAIN}/legal/privacy-policy-2022.pdf`}>
                            Privacy Policy
                        </ActiveLink>
                    </div>
                    {isCustomDomain && (
                        <div data-testid="logo" className="mb-2">
                            <p>Powered by</p>
                            <Logo className="!text-lg" />
                        </div>
                    )}
                </div>
            </DynamicContainer>
        </div>
    );
}

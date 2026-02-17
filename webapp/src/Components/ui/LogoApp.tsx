'use client';

import { useAppSelector } from '@app/store/hooks';
import Link from 'next/link';
import Image from 'next/image';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface ILogoProps {
    isCustomDomain?: boolean;
    isFooter?: boolean;
    isClientDomain?: boolean;
}

export default function LogoApp({ isCustomDomain, isFooter, isClientDomain }: ILogoProps) {
    const workspace = useAppSelector(selectWorkspace);
    const adminDomainUrl = `/${workspace?.workspaceName ? workspace?.workspaceName + '/' : ''}dashboard/forms`;

    return (
        <Link href={isClientDomain || isCustomDomain ? '/' : adminDomainUrl}>
            <Image
                src={isFooter ? '/images/logo-white.svg' : '/images/logo.svg'}
                alt="Logo"
                width={isFooter ? 150 : 120}
                height={40}
                className="cursor-pointer"
            />
        </Link>
    );
}

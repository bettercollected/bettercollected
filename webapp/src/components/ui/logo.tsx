import React from 'react';

import AnchorLink from '@app/components/ui/links/anchor-link';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface ILogo {
    className?: string;
    [props: string]: any;
}

const Logo: React.FC<React.SVGAttributes<{}>> = ({ className, ...props }: ILogo) => {
    const workspace = useAppSelector(selectWorkspace);

    return (
        <AnchorLink href={`/${workspace?.workspaceName}/dashboard`} className="flex items-center w-fit outline-none" {...props}>
            <div className={`text-[28px] font-semibold leading-8 ${className}`}>
                <span className="text-brand-500">Better</span>
                <span className="text-black-900">Collected.</span>
            </div>
        </AnchorLink>
    );
};

Logo.defaultProps = {
    className: ''
};
export default Logo;

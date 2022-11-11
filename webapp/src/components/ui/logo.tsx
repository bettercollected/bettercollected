import React from 'react';

import AnchorLink from '@app/components/ui/links/anchor-link';

const Logo: React.FC<React.SVGAttributes<{}>> = (props) => (
    <AnchorLink href="/" className="flex items-center w-fit outline-none" {...props}>
        <div className="text-2xl md:text-3xl lg:text-4xl">
            <span className="text-brand tracking-widest font-extrabold">Better</span>
            <span className="text-blue-500 tracking-widest font-black">Collected.</span>
        </div>
    </AnchorLink>
);

export default Logo;

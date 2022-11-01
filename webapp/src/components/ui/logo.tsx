import React, { useEffect, useState } from 'react';

import { Cardano } from '@app/components/icons/brands/cardano';
import AnchorLink from '@app/components/ui/links/anchor-link';
import { useLocalStorage } from '@app/lib/hooks/use-local-storage';

const Logo: React.FC<React.SVGAttributes<{}>> = (props) => {
    const [themeColor] = useLocalStorage<string>('cnft-color');

    const [fillColor, setFillColor] = useState('#ffa500');

    useEffect(() => {
        if (themeColor) {
            setFillColor(themeColor);
        }
    }, [themeColor]);

    return (
        <AnchorLink href="/" className="flex items-center w-fit outline-none" {...props}>
            <span className="relative flex overflow-hidden mr-1 md:mr-2">
                <Cardano fill={fillColor} width={40} height={40} />
            </span>
            <div className="font-header text-xl md:text-2xl lg:text-3xl font-semibold">
                <span className="mx-2 text-brand">CNFT</span>
                <span className="text-brand">|</span>
                <span className="mx-2 text-red-500">SALE</span>
            </div>
        </AnchorLink>
    );
};

export default Logo;

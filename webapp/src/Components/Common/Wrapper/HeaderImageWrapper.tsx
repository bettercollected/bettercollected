import React, { ReactNode } from 'react';

import Image from 'next/image';

export default function HeaderImageWrapper({ children, className }: { children?: ReactNode; className?: string }) {
    return (
        <div className="h-screen w-screen bg-white flex flex-col items-center">
            <div className=" w-full aspect-banner-mobile  lg:aspect-thank_you_cover  relative flex items-center justify-center">
                <Image src="/images/thankyou_cover.png" layout="fill" objectFit="cover" alt="ALternative" />
            </div>
            <div className={'px-5 flex flex-col items-center ' + className}>{children}</div>
        </div>
    );
}

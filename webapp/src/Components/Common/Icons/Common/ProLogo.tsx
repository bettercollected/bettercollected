import React from 'react';

import Pro from '@Components/Common/Icons/Dashboard/Pro';

export default function ProLogo() {
    return (
        <div className="flex items-center rounded gap-[2px] h-5 sm:h-6 p-1 sm:p-[6px] text-[10px] sm:body5 uppercase !leading-none !font-semibold !text-white bg-brand-500">
            <Pro width={12} height={12} />
            <span className="leading-none">Pro</span>
        </div>
    );
}
import React from 'react';

import Pro from './Pro';

export default function ProLogo() {
    return (
        <div className="sm:body5 flex h-5 items-center gap-[2px] rounded bg-brand-500 p-1 text-[10px] !font-semibold uppercase !leading-none !text-white sm:h-6 sm:p-[6px]">
            <Pro width={12} height={12} />
            <span className="leading-none">Pro</span>
        </div>
    );
}

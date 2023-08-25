import React from 'react';

import Logo from '@app/components/ui/logo';

export default function PoweredBy() {
    return (
        <div className="px-3 fixed bottom-4 right-4 py-2 flex gap-2 bg-white items-center rounded drop-shadow-lg ">
            <span className="body3 text-black-700">Powered by:</span>
            <Logo showProTag={false} isFooter isCustomDomain />
        </div>
    );
}

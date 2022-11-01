import React from 'react';

import Loader from '@app/components/ui/loader';

export default function FullScreenLoader() {
    return (
        <div className="!z-[99990] flex min-h-[80vh] w-full justify-center items-center">
            <Loader />
        </div>
    );
}

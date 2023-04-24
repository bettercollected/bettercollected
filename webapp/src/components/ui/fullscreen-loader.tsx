import React from 'react';

import Loader from '@app/components/ui/loader';

export default function FullScreenLoader() {
    return (
        <div data-testid="full-screen-loader" className="!z-[99990] flex min-h-[80vh] w-full justify-center items-center">
            <Loader variant="blink" />
        </div>
    );
}

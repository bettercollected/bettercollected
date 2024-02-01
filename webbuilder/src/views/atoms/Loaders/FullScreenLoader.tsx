import React from 'react';

import Loader from './Loader';

export default function FullScreenLoader() {
    return (
        <div
            data-testid="full-screen-loader"
            className="!z-[99990] flex min-h-[100vh] w-full items-center justify-center"
        >
            <Loader variant="blink" />
        </div>
    );
}

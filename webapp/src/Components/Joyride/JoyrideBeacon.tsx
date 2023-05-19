import React from 'react';

export default class BeaconComponent extends React.Component {
    render(): React.ReactNode {
        return (
            <span className="relative flex justify-center items-center h-5 w-5 cursor-pointer !z-[3000]" {...this.props}>
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-accent-600 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-brand-accent"></span>
            </span>
        );
    }
}

import React from 'react';

export default class BeaconComponent extends React.Component {
    onBeaconClick = (e: any, props: any) => {
        e.preventDefault();
        e.stopPropagation();

        if (!!props.onClick) {
            props.onClick(e);
        }
    };

    render(): React.ReactNode {
        return (
            <span
                className="flex h-4 w-4 cursor-pointer items-center justify-center rounded-full"
                {...this.props}
                onClick={(e: any) => this.onBeaconClick(e, this.props)}
            >
                <span className="absolute h-5 w-5 animate-ping rounded-full bg-[#FFB44780]"></span>
                <span className="relative h-4 w-4 rounded-full bg-orange-500"></span>
            </span>
        );
    }
}

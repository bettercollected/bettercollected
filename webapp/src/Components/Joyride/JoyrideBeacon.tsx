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
            <span className="flex justify-center items-center h-4 w-4 rounded-full cursor-pointer" {...this.props} onClick={(e: any) => this.onBeaconClick(e, this.props)}>
                <span className="animate-ping absolute h-5 w-5 rounded-full bg-[#FFB44780]"></span>
                <span className="relative rounded-full h-4 w-4 bg-orange-500"></span>
            </span>
        );
    }
}

import React from 'react';

import Image from 'next/image';

export function PinOutlinedIcon(props: any) {
    const { height, width } = props;

    return (
        <div onClick={() => props.clickButton()}>
            <Image
                src="https://img.icons8.com/ios/50/null/pin--v1.png"
                width={width || 19}
                height={height || 19}
                alt="Pin Outlined Icon"
            />
        </div>
    );
}

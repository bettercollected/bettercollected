import React from 'react';

export function PinOutlinedIcon(props: any) {
    const { height, width } = props;

    return (
        <div onClick={() => props.clickButton()}>
            <img src="https://img.icons8.com/ios/50/null/pin--v1.png" width={!!width ? width : 19} height={!!height ? height : 19} />
        </div>
    );
}

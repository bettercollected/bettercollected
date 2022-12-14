import React from 'react';

import Tooltip from '@mui/material/Tooltip';

export function PinOutlinedIcon(props: any) {
    const { height, width } = props;

    return (
        <Tooltip title="pin the form">
            <div onClick={() => props.clickButton()}>
                <img src="https://img.icons8.com/ios/50/null/pin--v1.png" width={!!width ? width : 19} height={!!height ? height : 19} />
            </div>
        </Tooltip>
    );
}

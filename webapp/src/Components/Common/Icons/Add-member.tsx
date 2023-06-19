import React, { SVGAttributes } from 'react';

export default function AddMember(props: SVGAttributes<{}>) {
    return (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path
                d="M13.3332 5.66667V9M11.6665 7.33333H14.9998M5.33317 10H10.6665C12.1393 10 13.3332 11.1939 13.3332 12.6667V14H2.6665V12.6667C2.6665 11.1939 3.86041 10 5.33317 10ZM10.6665 4.66667C10.6665 6.13943 9.4726 7.33333 7.99984 7.33333C6.52708 7.33333 5.33317 6.13943 5.33317 4.66667C5.33317 3.19391 6.52708 2 7.99984 2C9.4726 2 10.6665 3.19391 10.6665 4.66667Z"
                stroke="#343A40"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

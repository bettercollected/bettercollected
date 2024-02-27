import React from 'react';

export function TextOutlinedIcon(props: React.SVGAttributes<any>) {
    return (
        <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <rect width="20" height="20" rx="4" fill="#AAAAAA" />
            <path
                d="M11.8476 15H7.97563V13.736H9.35163V5.064H6.83963V6.264H5.57563V3.8H14.4236V6.264H13.1596V5.064H10.6796V13.736H11.8476V15Z"
                fill="white"
            />
        </svg>
    );
}

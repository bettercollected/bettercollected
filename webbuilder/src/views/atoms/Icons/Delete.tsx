import React from 'react';

export default function DeleteIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M16.75 4.35294V16.7647C16.75 17.9992 15.7426 19 14.5 19H5.5C4.25736 19 3.25 17.9992 3.25 16.7647V4.35294M1 4.35294H19M13.375 4.35294V3.23529C13.375 2.00078 12.3676 1 11.125 1H8.875C7.63236 1 6.625 2.00078 6.625 3.23529V4.35294"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

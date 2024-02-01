import React from 'react';

export default function PrivateIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M5.33301 7.33333V4.66667C5.33301 3.77778 5.86634 2 7.99967 2C10.133 2 10.6663 3.77778 10.6663 4.66667V7.33333M5.33301 7.33333H3.33301V14H12.6663V7.33333H10.6663M5.33301 7.33333H10.6663"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

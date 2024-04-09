import React from 'react';

export default function Billing({ props }: any) {
    return (
        <svg
            width="20"
            height="14"
            viewBox="0 0 20 14"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <rect
                x="0.5"
                y="0.5"
                width="19"
                height="13"
                rx="1.5"
                stroke="currentColor"
            />
            <path d="M0 5L20 5" stroke="currentColor" />
            <path d="M11 9L16 9" stroke="currentColor" strokeLinecap="round" />
        </svg>
    );
}

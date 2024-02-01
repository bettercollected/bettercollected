import React from 'react';

export function FormIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M9 14H15M9 4.5H5V21H19V4.5H15M9 4.5V6H15V4.5M9 4.5V3H15V4.5"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

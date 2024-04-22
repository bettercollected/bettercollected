import React from 'react';

export function MobileIcon(props: React.SVGAttributes<any>) {
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
                d="M10 14.5083V14.5M6.66667 2H13.3333C14.2538 2 15 2.74619 15 3.66667V15.3333C15 16.2538 14.2538 17 13.3333 17H6.66667C5.74619 17 5 16.2538 5 15.3333V3.66667C5 2.74619 5.74619 2 6.66667 2Z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

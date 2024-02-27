import React from 'react';

export function PlusOutlined(props: React.SVGAttributes<any>) {
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
                d="M10 5L10 15"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
            />
            <path d="M5 10H15" stroke="white" strokeWidth="2" strokeLinecap="round" />
        </svg>
    );
}

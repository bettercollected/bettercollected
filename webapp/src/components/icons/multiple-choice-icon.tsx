import React from 'react';

export default function MultipleChoiceIcon(props: React.SVGAttributes<any>) {
    return (
        <svg
            width="40"
            height="40"
            viewBox="0 0 40 40"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <rect
                x="5.5"
                y="4"
                width="30"
                height="30"
                rx="5"
                stroke="currentColor"
                strokeWidth="2"
            />
            <path
                d="M27.5 15L17.8751 24L13.5 19.9091"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

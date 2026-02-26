import React from 'react';

export default function RequiredIcon(props: React.SVGAttributes<any>) {
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
                d="M6 12.2695L14.0001 7.72927"
                stroke="currentColor"
                strokeWidth={props.strokeWidth || 2}
                strokeLinecap="round"
            />
            <path
                d="M6 7.73047L14.0001 12.2707"
                stroke="currentColor"
                strokeWidth={props.strokeWidth || 2}
                strokeLinecap="round"
            />
            <path
                d="M10 14L10 6"
                stroke="currentColor"
                strokeWidth={props.strokeWidth || 2}
                strokeLinecap="round"
            />
        </svg>
    );
}

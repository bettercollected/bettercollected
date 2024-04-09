import React from 'react';

export function LogicIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg
            width="22"
            height="15"
            viewBox="0 0 22 15"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M1 12H6.6321C7.29156 12 7.90862 11.6749 8.28156 11.1311L13.2613 3.86894C13.6342 3.32507 14.2513 3 14.9108 3H19"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
            />
            <path
                d="M1 3H6.6321C7.29156 3 7.90862 3.32507 8.28156 3.86894L13.2613 11.1311C13.6342 11.6749 14.2513 12 14.9108 12H19"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
            />
            <path
                d="M18 10L20 12L18 14"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
            />
            <path
                d="M18 1L20 3L18 5"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
            />
        </svg>
    );
}

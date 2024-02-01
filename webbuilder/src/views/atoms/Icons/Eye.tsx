import React from 'react';

export default function Eye(props: React.SVGAttributes<{}>) {
    return (
        <svg
            width="20"
            height="14"
            viewBox="0 0 20 14"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M10 1C4.27273 1 1 7 1 7C1 7 4.27273 13 10 13C15.7273 13 19 7 19 7C19 7 15.7273 1 10 1Z"
                stroke="#6E6E6E"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <path
                d="M10 9.57143C11.4912 9.57143 12.7 8.42016 12.7 7C12.7 5.57984 11.4912 4.42857 10 4.42857C8.50883 4.42857 7.3 5.57984 7.3 7C7.3 8.42016 8.50883 9.57143 10 9.57143Z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

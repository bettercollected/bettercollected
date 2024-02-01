import React from 'react';

export function Ranking(props: React.SVGAttributes<{}>) {
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
                d="M16.5 10.875V17.625M12 6.375L12 17.625M7.5 14.25L7.5 17.625M3 3H21V21H3V3Z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

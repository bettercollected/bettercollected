import React from 'react';

export function LinkHorizontalIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            {...props}
        >
            <path
                d="M15 16H17C19.2091 16 21 14.2091 21 12C21 9.79086 19.2091 8 17 8H15M8 12H16M9 8H7C4.79086 8 3 9.79086 3 12C3 14.2091 4.79086 16 7 16H9"
                stroke="#4D4D4D"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
            />
        </svg>
    );
}

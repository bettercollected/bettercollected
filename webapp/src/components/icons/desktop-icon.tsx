import React from 'react';

export function DesktopIcon(props: React.SVGAttributes<any>) {
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
                d="M10 18H14M10 18H6M10 18V14M10 14H3C2.44772 14 2 13.5523 2 13V4C2 3.44771 2.44772 3 3 3H17C17.5523 3 18 3.44772 18 4V13C18 13.5523 17.5523 14 17 14H10Z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

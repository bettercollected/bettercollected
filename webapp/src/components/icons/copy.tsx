import React from 'react';

export default function CopyIcon(props: React.SVGAttributes<any>) {
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
                d="M15.5 12H17C18.1046 12 19 11.1046 19 10V3C19 1.89543 18.1046 1 17 1H10C8.89543 1 8 1.89543 8 3V4.5M3 8H10C11.1046 8 12 8.89543 12 10V17C12 18.1046 11.1046 19 10 19H3C1.89543 19 1 18.1046 1 17V10C1 8.89543 1.89543 8 3 8Z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

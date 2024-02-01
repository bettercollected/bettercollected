import React from 'react';

export default function Element(props: React.SVGAttributes<any>) {
    return (
        <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <rect
                x="4"
                y="7"
                width="17"
                height="9"
                rx="2"
                stroke="currentColor"
                strokeWidth="2"
            />
        </svg>
    );
}

import React from 'react';

export default function ElementsWithLabel(props: React.SVGAttributes<any>) {
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
                y="11"
                width="17"
                height="9"
                rx="2"
                stroke="currentColor"
                strokeWidth="2"
            />
            <rect
                x="3.5"
                y="4.5"
                width="8.9"
                height="3"
                rx="0.5"
                fill="currentColor"
                stroke="currentColor"
            />
        </svg>
    );
}

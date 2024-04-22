import React from 'react';

export default function PlusIcon(props: React.SVGAttributes<any>) {
    return (
        <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path d="M8 3L8 13" stroke="currentColor" strokeLinecap="round" />
            <path d="M3 8H13" stroke="currentColor" strokeLinecap="round" />
        </svg>
    );
}

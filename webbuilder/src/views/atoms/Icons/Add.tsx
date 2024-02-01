import React from 'react';

export function AddIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="25"
            viewBox="0 0 24 25"
            fill="none"
            {...props}
        >
            <path
                d="M12 6.5L12 18.5"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
            />
            <path d="M6 12.5H18" stroke="white" strokeWidth="2" strokeLinecap="round" />
        </svg>
    );
}

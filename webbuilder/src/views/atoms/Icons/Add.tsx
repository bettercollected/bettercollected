import React from 'react';

export function AddIcon(props: React.SVGAttributes<{}> & Readonly<{}>) {
    return (
        <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path d="M7 1V13" stroke="#4D4D4D" strokeWidth="2" strokeLinecap="round" />
            <path
                d="M1 7L13 7"
                stroke="#4D4D4D"
                strokeWidth="2"
                strokeLinecap="round"
            />
        </svg>
    );
}

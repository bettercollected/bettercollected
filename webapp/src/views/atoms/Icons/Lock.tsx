import React from 'react';

export default function LockIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M5.33398 7.33333V4.66667C5.33398 3.77778 5.86732 2 8.00065 2C10.134 2 10.6673 3.77778 10.6673 4.66667V7.33333M5.33398 7.33333H3.33398V14H12.6673V7.33333H10.6673M5.33398 7.33333H10.6673"
                stroke="#343A40"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

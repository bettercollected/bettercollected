import React from 'react';

export default function Eye(props: React.SVGAttributes<{}>) {
    return (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path
                d="M8.00065 3.33301C3.75823 3.33301 1.33398 7.99967 1.33398 7.99967C1.33398 7.99967 3.75823 12.6663 8.00065 12.6663C12.2431 12.6663 14.6673 7.99967 14.6673 7.99967C14.6673 7.99967 12.2431 3.33301 8.00065 3.33301Z"
                stroke="#343A40"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <path
                d="M8.00065 9.99967C9.10522 9.99967 10.0007 9.10424 10.0007 7.99967C10.0007 6.8951 9.10522 5.99967 8.00065 5.99967C6.89608 5.99967 6.00065 6.8951 6.00065 7.99967C6.00065 9.10424 6.89608 9.99967 8.00065 9.99967Z"
                stroke="#343A40"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}
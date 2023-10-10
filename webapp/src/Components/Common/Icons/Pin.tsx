import React from 'react';

export default function Pin(props: React.SVGAttributes<{}>) {
    return (
        <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path d="M7.33268 8.66695L2.66602 13.3336M10.666 2.66699L13.3327 5.33366L9.99934 11.3337L4.66602 6.00033L10.666 2.66699Z" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
}
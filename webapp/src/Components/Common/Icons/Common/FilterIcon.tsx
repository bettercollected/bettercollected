import React from 'react';

export default function FilterIcon(props: React.SVGAttributes<any>) {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path d="M3 7H13" stroke="#2E2E2E" strokeWidth="2" strokeLinecap="round" />
            <path d="M3 12H21" stroke="#2E2E2E" strokeWidth="2" strokeLinecap="round" />
            <path d="M3 17H21" stroke="#2E2E2E" strokeWidth="2" strokeLinecap="round" />
        </svg>
    );
}

import React from 'react';

export function FormIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <rect x="5" y="4" width="14" height="16" rx="2" stroke="#212529" />
            <path d="M8 8H16" stroke="#212529" strokeLinecap="round" />
            <path d="M8 12H16" stroke="#212529" strokeLinecap="round" />
            <path d="M8 16H13" stroke="#212529" strokeLinecap="round" />
        </svg>
    );
}

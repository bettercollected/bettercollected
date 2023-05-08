import React from 'react';

export function FormIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <rect x="5" y="4" width="14" height="17" rx="2" stroke="currentColor" />
            <path d="M9 9H15" stroke="currentColor" strokeLinecap="round" />
            <path d="M9 13H15" stroke="currentColor" strokeLinecap="round" />
            <path d="M9 17H13" stroke="currentColor" strokeLinecap="round" />
        </svg>
    );
}

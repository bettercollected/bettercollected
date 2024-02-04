import React from 'react';

export default function GreenShield(props: React.SVGAttributes<any>) {
    return (
        <svg width="76" height="76" viewBox="0 0 76 76" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <circle cx="38" cy="38" r="38" fill="#D7FFF6" />
            <rect x="14" y="14" width="48" height="48" rx="24" fill="#2DBB7F" />
            <path d="M42.375 34.9444L36.75 40.4444L34.875 38.6111M38 27L28 31.8889C28 38.2362 31.4804 47.1786 38 49C44.5196 47.1786 48 38.2362 48 31.8889L38 27Z" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
}

import React from 'react';

export default function GreenCheckedCircle(props: React.SVGAttributes<any>) {
    return (
        <svg width="76" height="76" viewBox="0 0 76 76" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <circle cx="38" cy="38" r="38" fill="#D7FFF6" />
            <rect x="14" y="14" width="48" height="48" rx="24" fill="#2DBB7F" />
            <path d="M31 39.8421L35.0137 43L45 33" stroke="white" strokeWidth="2" strokeLinecap="round" />
        </svg>
    );
}

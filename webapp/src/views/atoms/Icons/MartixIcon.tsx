import React from 'react';

export default function MatrixIcon(props: React.SVGProps<SVGSVGElement>) {
    return (
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <rect x="7" y="7" width="11" height="11" rx="2" stroke="currentColor" strokeWidth="2" />
            <rect x="7" y="22" width="11" height="11" rx="2" stroke="currentColor" strokeWidth="2" />
            <rect x="22" y="7" width="11" height="11" rx="2" stroke="currentColor" strokeWidth="2" />
            <rect x="22" y="22" width="11" height="11" rx="2" stroke="currentColor" strokeWidth="2" />
            <path d="M25 13L26.25 14L30 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M10 28L11.25 29L15 26" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
    );
}

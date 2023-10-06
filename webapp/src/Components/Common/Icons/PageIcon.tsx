import React from 'react';

export default function PageIcon(props: React.SVGAttributes<any>) {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path d="M13 3H5V21H19V9M13 3H14L19 8V9M13 3V7C13 8 14 9 15 9H19" stroke="#6C757D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
}
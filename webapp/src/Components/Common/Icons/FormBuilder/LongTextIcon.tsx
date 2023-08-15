import React from 'react';

export default function LongTextIcon(props: React.SVGAttributes<any>) {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path d="M3 7L13 7" stroke="#343A40" strokeWidth="2" strokeLinecap="round" />
            <path d="M3 12L21 12" stroke="#343A40" strokeWidth="2" strokeLinecap="round" />
            <path d="M3 17H21" stroke="#343A40" strokeWidth="2" strokeLinecap="round" />
        </svg>
    );
}

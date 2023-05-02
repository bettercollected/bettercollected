import React from 'react';

export default function Chevron({ props }: any) {
    return (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path d="M16 7L10 13L4 7" stroke="currentColor" strokeLinecap="round" />
        </svg>
    );
}

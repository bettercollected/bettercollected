import React from 'react';

export function PlusIcon(props: React.SVGAttributes<any>) {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path d="M12 6L12 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <path d="M6 12H18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
    );
}

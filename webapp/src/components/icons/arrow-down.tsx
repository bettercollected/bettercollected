import React from 'react';

export const ArrowDown: React.FC<React.SVGAttributes<{}>> = (props) => {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <rect width="24" height="24" fill="white" />
            <path d="M4 8L12 16L20 8" stroke="#4D4D4D" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
    );
};

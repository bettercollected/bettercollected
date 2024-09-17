import React from 'react';

export const ChevronForward: React.FC<React.SVGAttributes<{}>> = (props) => {
    return (
        <svg
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path d="M4 10L8 6L4 2" stroke="currentColor" strokeLinecap="round" />
        </svg>
    );
};

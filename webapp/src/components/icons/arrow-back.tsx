import React from 'react';

export const ArrowBack: React.FC<React.SVGAttributes<{}>> = (props) => {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path d="M15 6L9 12L15 18" stroke="#4D4D4D" stroke-width="2" stroke-linecap="round" />
        </svg>
    );
};

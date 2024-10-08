import React from 'react';

export const DropdownCloseIcon = (props: React.SVGAttributes<any>) => {
    return (
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" {...props}>
            <path d="M19 5L5 19M5.00001 5L19 19" stroke="#4D4D4D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
}

export default DropdownCloseIcon;

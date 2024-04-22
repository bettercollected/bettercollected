import React from 'react';

export const Check: React.FC<React.SVGAttributes<{}>> = (props) => {
    return (
        <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M4 11L7.27273 14L16 6"
                stroke={props?.color ?? '#212529'}
                strokeLinecap="round"
            />
        </svg>
    );
};

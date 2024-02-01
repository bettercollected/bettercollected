import React from 'react';

export const LinkIcon: React.FC<React.SVGAttributes<{}>> = (props) => {
    return (
        <svg
            width="20"
            height="10"
            viewBox="0 0 20 10"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M13 9H15C17.2091 9 19 7.20914 19 5C19 2.79086 17.2091 1 15 1H13M6 5H14M7 1H5C2.79086 1 1 2.79086 1 5C1 7.20914 2.79086 9 5 9H7"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
};

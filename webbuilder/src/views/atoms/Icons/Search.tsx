import React from 'react';

export const SearchIcon: React.FC<React.SVGAttributes<{}>> = (props) => {
    return (
        <svg
            width="22"
            height="22"
            viewBox="0 0 22 22"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <circle cx="9.57143" cy="9.57143" r="8.57143" stroke="currentColor" />
            <path
                d="M21.0006 20.9996L16.7148 16.7139"
                stroke="currentColor"
                strokeLinecap="round"
            />
        </svg>
    );
};

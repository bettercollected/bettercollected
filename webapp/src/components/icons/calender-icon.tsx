import React from 'react';

export const CalenderIcon: React.FC<React.SVGAttributes<{}>> = (props) => {
    return (
        <svg
            width="40"
            height="40"
            viewBox="0 0 40 40"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M32.5 18.4444H7.5M32.5 18.4444V30.8889C32.5 32.6071 31.1009 34 29.375 34H10.625C8.89911 34 7.5 32.6071 7.5 30.8889V12.2222C7.5 10.504 8.89911 9.11111 10.625 9.11111H29.375C31.1009 9.11111 32.5 10.504 32.5 12.2222V18.4444ZM24.6875 6V12.2222M15.3125 6V12.2222"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
            />
        </svg>
    );
};

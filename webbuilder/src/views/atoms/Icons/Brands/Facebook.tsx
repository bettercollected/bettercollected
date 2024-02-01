import React from 'react';

export function Facebook(props: React.SVGAttributes<{}>) {
    return (
        <svg
            width="26"
            height="26"
            viewBox="0 0 26 26"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <circle cx="13" cy="13" r="13" fill="#1877F2" />
            <path
                d="M16.4103 15.0485L16.8767 11.8155H13.9589V9.71751C13.9589 8.83302 14.3665 7.97088 15.6734 7.97088H17V5.21846C17 5.21846 15.796 5 14.645 5C12.2419 5 10.6712 6.54835 10.6712 9.35146V11.8155H8V15.0485H10.6712V22.8641C11.2069 22.9535 11.7558 23 12.3151 23C12.8743 23 13.4233 22.9535 13.9589 22.8641V15.0485H16.4103Z"
                fill="white"
            />
        </svg>
    );
}

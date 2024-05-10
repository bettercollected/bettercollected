import React from 'react';

export default function Inbox(props: React.SVGAttributes<{}>) {
    return (
        <svg
            width="38"
            height="34"
            viewBox="0 0 38 34"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M1 17H12L15 23H23L27 17H37M1 17V29C1 31.2091 2.79086 33 5 33H33C35.2091 33 37 31.2091 37 29V17M1 17L6.51334 2.29775C6.80607 1.51714 7.55231 1 8.386 1H29.614C30.4477 1 31.1939 1.51715 31.4867 2.29775L37 17"
                stroke="#495057"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

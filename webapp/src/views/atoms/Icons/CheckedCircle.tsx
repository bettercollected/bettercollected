import React from 'react';

export default function CheckedCircle(props: React.SVGAttributes<any>) {
    return (
        <svg
            width="76"
            height="76"
            viewBox="0 0 76 76"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <circle cx="38" cy="38" r="38" fill="#D7FFF6" />
            <circle cx="38" cy="38" r="23" fill="#3CC8AA" />
            <path
                d="M30 40.7551L34.4308 45L48 32"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
            />
        </svg>
    );
}

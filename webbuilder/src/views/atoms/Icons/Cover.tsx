import React from 'react';

export default function CoverIcon(props: React.SVGAttributes<any>) {
    return (
        <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M9.00002 5H4.00004L4 9M20 9V5.00004L15 5M15 19.0001H20L20 15M4 15L4 19L9.00002 19.0001"
                stroke="#6C757D"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

import React from 'react';

export default function DeleteIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path
                d="M18.75 6.35294V18.7647C18.75 19.9992 17.7426 21 16.5 21H7.5C6.25736 21 5.25 19.9992 5.25 18.7647V6.35294M3 6.35294H21M15.375 6.35294V5.23529C15.375 4.00078 14.3676 3 13.125 3H10.875C9.63236 3 8.625 4.00078 8.625 5.23529V6.35294"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

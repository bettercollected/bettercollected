import React from 'react';

export default function EllipsisOption({ props }: any) {
    return (
        <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{
                rotate: '90deg'
            }}
            {...props}
        >
            <circle
                cx="4"
                cy="12"
                r="2"
                transform="rotate(-90 4 12)"
                fill="currentColor"
            />
            <circle
                cx="12"
                cy="12"
                r="2"
                transform="rotate(-90 12 12)"
                fill="currentColor"
            />
            <circle
                cx="20"
                cy="12"
                r="2"
                transform="rotate(-90 20 12)"
                fill="currentColor"
            />
        </svg>
    );
}

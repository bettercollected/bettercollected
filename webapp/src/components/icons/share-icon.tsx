import React from 'react';

export default function ShareIcon(props: React.SVGAttributes<{}>) {
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
                d="M6.68439 8.65778L13.3125 5.34375M13.3156 14.6578L6.6938 11.3469M19 4C19 5.65685 17.6569 7 16 7C14.3431 7 13 5.65685 13 4C13 2.34315 14.3431 1 16 1C17.6569 1 19 2.34315 19 4ZM7 10C7 11.6569 5.65685 13 4 13C2.34315 13 1 11.6569 1 10C1 8.34315 2.34315 7 4 7C5.65685 7 7 8.34315 7 10ZM19 16C19 17.6569 17.6569 19 16 19C14.3431 19 13 17.6569 13 16C13 14.3431 14.3431 13 16 13C17.6569 13 19 14.3431 19 16Z"
                stroke="currentColor"
                strokeWidth={props.strokeWidth || 2}
            />
        </svg>
    );
}

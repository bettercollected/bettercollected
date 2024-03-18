import React from 'react';

export default function RatingIcon(props: React.SVGAttributes<any>) {
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
                d="M20 29.0588L10.3333 34L12.75 24.1176L5.5 15.8824L15.9722 15.0588L20 6L24.0278 15.0588L34.5 15.8824L27.25 24.1176L29.6667 34L20 29.0588Z"
                stroke="#6E6E6E"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
            />
        </svg>
    );
}

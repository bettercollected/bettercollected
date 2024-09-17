import React from 'react';

export default function PublicIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M14 8C14 11.3137 11.3137 14 8 14M14 8C14 4.68629 11.3137 2 8 2M14 8H2M8 14C4.68629 14 2 11.3137 2 8M8 14C8 14 10.6667 12 10.6667 8C10.6667 4 8 2 8 2M8 14C8 14 5.33333 12 5.33333 8C5.33333 4 8 2 8 2M2 8C2 4.68629 4.68629 2 8 2"
                stroke="currentColor"
            />
        </svg>
    );
}

import React from 'react';

export function MediaOutlinedIcon(props: React.SVGAttributes<any>) {
    return (
        <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <rect width="20" height="20" rx="4" fill="#AAAAAA" />
            <path
                d="M4.0202 14.7468C4.13788 15.4578 4.75562 16 5.5 16H14.5C15.3284 16 16 15.3284 16 14.5V11.6426M4.0202 14.7468C4.00691 14.6665 4 14.584 4 14.5V5.5C4 4.67157 4.67157 4 5.5 4H14.5C15.3284 4 16 4.67157 16 5.5V11.6426M4.0202 14.7468L6.88572 11.8813C7.39574 11.435 8.14164 11.3861 8.70552 11.762L9.08737 12.0166C9.63088 12.379 10.3464 12.3479 10.8565 11.9398L12.8426 10.3509C13.3488 9.94596 14.0539 9.91418 14.5921 10.2613C14.6518 10.2998 14.7048 10.3474 14.755 10.3976L16 11.6426"
                stroke="white"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <circle cx="7.5" cy="7.5" r="1.5" fill="white" />
        </svg>
    );
}

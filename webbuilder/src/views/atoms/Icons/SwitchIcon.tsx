import React from 'react';

export function SwitchIcon(props: React.SVGAttributes<any>) {
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
                d="M6.16667 14.4C6.76124 15.6047 7.77121 16.6014 9.04442 17.24C10.3176 17.8786 11.7851 18.1245 13.2257 17.9406C15.5802 17.6401 17.2212 16.0661 19 14.6177M19 18V14.4H15.5M17.8333 9.6C17.2388 8.39531 16.2288 7.39857 14.9556 6.75997C13.6824 6.12136 12.2149 5.87549 10.7743 6.05939C8.41981 6.35994 6.77879 7.93394 5 9.38234M5 6V9.6H8.5"
                stroke="#0764EB"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

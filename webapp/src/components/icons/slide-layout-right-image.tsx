import React from 'react';

export default function SlideLayoutRightImage(props: React.SVGAttributes<any>) {
    return (
        <svg
            width="68"
            height="41"
            viewBox="0 0 68 41"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <rect x="36" width="32" height="41" rx="4" fill="#D0D5DD" />
            <rect y="12" width="15" height="4" rx="2" fill="#344054" />
            <rect y="20" width="30" height="8" rx="2" fill="white" stroke="#D0D5DD" />
        </svg>
    );
}

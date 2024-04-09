import React from 'react';

export default function SlideLayoutNoImage(props: React.SVGAttributes<any>) {
    return (
        <svg
            width="82"
            height="51"
            viewBox="0 0 82 51"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <rect x="0.5" y="0.5" width="81" height="50" rx="8.5" fill="white" />
            <rect x="33.5" y="17" width="15" height="4" rx="2" fill="#D9D9D9" />
            <rect x="26" y="25" width="30" height="8" rx="2" fill="#D9D9D9" />
        </svg>
    );
}

import React from 'react';

export default function CircleOutlinedIcon(props: React.SVGAttributes<any>) {
    return (
        <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <circle cx="12" cy="12" r="8" stroke="#6C757D" strokeWidth="2" />
        </svg>
    );
}

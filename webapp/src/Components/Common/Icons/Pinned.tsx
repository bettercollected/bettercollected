import React from 'react';

export default function PinnedIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path opacity="0.15" d="M13.3335 3.33325L16.6668 6.66659L12.5002 14.1666L5.8335 7.49992L13.3335 3.33325Z" fill="#0764EB" />
            <path d="M9.16683 10.8332L3.3335 16.6665M13.3335 3.33325L16.6668 6.66659L12.5002 14.1666L5.8335 7.49992L13.3335 3.33325Z" stroke="#0764EB" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
}

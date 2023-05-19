import React from 'react';

export default function ResponderIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path
                d="M19.2222 18.9993V17.2216C19.2222 16.2786 18.8476 15.3742 18.1808 14.7074C17.514 14.0406 16.6097 13.666 15.6667 13.666H8.55556C7.61256 13.666 6.70819 14.0406 6.0414 14.7074C5.3746 15.3742 5 16.2786 5 17.2216V18.9993"
                stroke="#212529"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <path
                d="M12.1122 11.1111C14.0759 11.1111 15.6678 9.51923 15.6678 7.55556C15.6678 5.59188 14.0759 4 12.1122 4C10.1485 4 8.55664 5.59188 8.55664 7.55556C8.55664 9.51923 10.1485 11.1111 12.1122 11.1111Z"
                stroke="#212529"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

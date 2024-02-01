import React, { SVGAttributes } from 'react';

export default function AddMember(props: SVGAttributes<{}>) {
    return (
        <svg
            width="22"
            height="18"
            viewBox="0 0 22 18"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M17.3636 11.6667C19.3719 11.6667 21 13.2585 21 15.2222V17H19.1818M14.6364 7.99909C16.2048 7.60438 17.3636 6.21229 17.3636 4.55555C17.3636 2.8988 16.2048 1.50671 14.6364 1.11201M11.9091 4.55556C11.9091 6.51923 10.281 8.11111 8.27273 8.11111C6.26442 8.11111 4.63636 6.51923 4.63636 4.55556C4.63636 2.59188 6.26442 1 8.27273 1C10.281 1 11.9091 2.59188 11.9091 4.55556ZM4.63636 11.6667H11.9091C13.9174 11.6667 15.5455 13.2585 15.5455 15.2222V17H1V15.2222C1 13.2585 2.62806 11.6667 4.63636 11.6667Z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

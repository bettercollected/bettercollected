import React, { SVGAttributes } from 'react';

export default function Preview(props: SVGAttributes<{}>) {
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
                d="M8.00016 3.3335C3.75774 3.3335 1.3335 8.00016 1.3335 8.00016C1.3335 8.00016 3.75774 12.6668 8.00016 12.6668C12.2426 12.6668 14.6668 8.00016 14.6668 8.00016C14.6668 8.00016 12.2426 3.3335 8.00016 3.3335Z"
                stroke="#343A40"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <path
                d="M8.00016 10.0002C9.10473 10.0002 10.0002 9.10473 10.0002 8.00016C10.0002 6.89559 9.10473 6.00016 8.00016 6.00016C6.89559 6.00016 6.00016 6.89559 6.00016 8.00016C6.00016 9.10473 6.89559 10.0002 8.00016 10.0002Z"
                stroke="#343A40"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

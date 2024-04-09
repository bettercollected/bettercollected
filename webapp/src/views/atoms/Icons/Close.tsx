import React from 'react';

import cn from 'classnames';

export function Close(props: React.SVGAttributes<{}>) {
    const { className, ...otherProps } = props;
    return (
        <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className={'cursor-pointer ' + className}
            {...otherProps}
        >
            <path
                d="M19 5L5 19M5.00001 5L19 19"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

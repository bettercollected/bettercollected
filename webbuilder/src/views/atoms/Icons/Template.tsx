import React from 'react';

export const TemplateIcon = (props: React.SVGAttributes<{}>) => {
    return (
        <svg
            width="20"
            height="16"
            viewBox="0 0 20 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M1 5H19M2.28571 1H17.7143C18.4244 1 19 1.56982 19 2.27273V13.7273C19 14.4302 18.4244 15 17.7143 15H2.28571C1.57563 15 1 14.4302 1 13.7273V2.27273C1 1.56982 1.57563 1 2.28571 1Z"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
};

import React from 'react';

export default function UploadIcon(props: React.SVGAttributes<any>) {
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
                d="M7 9.64706V8.70588C7 6.1069 9.23858 4 12 4C14.7614 4 17 6.1069 17 8.70588V9.64706C19.2091 9.64706 21 11.3326 21 13.4118C21 14.8052 20.1956 16.0549 19 16.7059M7 9.64706C4.79086 9.64706 3 11.3326 3 13.4118C3 14.8052 3.8044 16.0549 5 16.7059M7 9.64706C7.43285 9.64706 7.84965 9.71177 8.24006 9.83147M12 11.5294V20M12 11.5294L15 14.3529M12 11.5294L9 14.3529"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

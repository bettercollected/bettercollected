import React from 'react';

export const Refresh: React.FC<React.SVGAttributes<{}>> = (props) => {
    return (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path
                d="M1.17948 11.2338C1.81978 12.4941 2.90745 13.5369 4.2786 14.205C5.64974 14.873 7.23009 15.1303 8.78153 14.9379C11.3171 14.6234 13.0844 12.9768 15 11.4616M15 15V11.2338H11.2308M14.8205 4.76616C14.1802 3.50586 13.0925 2.46312 11.7214 1.79504C10.3503 1.12696 8.7699 0.869739 7.21847 1.06213C4.68288 1.37656 2.91562 3.0232 1 4.53845M1 1V4.76616H4.76923"
                stroke="#0764EB"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
            />
        </svg>
    );
};

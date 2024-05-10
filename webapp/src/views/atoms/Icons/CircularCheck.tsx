import React from 'react';

export default function CircularCheck(props: React.SVGAttributes<any>) {
    return (
        <svg
            width="41"
            height="41"
            viewBox="0 0 41 41"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <circle cx="20.5" cy="20.5" r="20.5" fill={props?.color || '#2DBB7F'} />
            <g filter="url(#filter0_d_4220_6128)">
                <path
                    d="M12 22.4082L15.5333 25.4409C15.908 25.7625 16.4613 25.7625 16.8359 25.4409L29 15"
                    stroke="white"
                    strokeWidth="4"
                    strokeLinecap="round"
                />
            </g>
            <defs>
                <filter
                    id="filter0_d_4220_6128"
                    x="5.99996"
                    y="12"
                    width="29.0001"
                    height="22.6826"
                    filterUnits="userSpaceOnUse"
                >
                    <feFlood floodOpacity="0" result="BackgroundImageFix" />
                    <feColorMatrix
                        in="SourceAlpha"
                        type="matrix"
                        values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0"
                        result="hardAlpha"
                    />
                    <feOffset dy="3" />
                    <feGaussianBlur stdDeviation="2" />
                    <feComposite in2="hardAlpha" operator="out" />
                    <feColorMatrix
                        type="matrix"
                        values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.15 0"
                    />
                    <feBlend
                        mode="normal"
                        in2="BackgroundImageFix"
                        result="effect1_dropShadow_4220_6128"
                    />
                    <feBlend
                        mode="normal"
                        in="SourceGraphic"
                        in2="effect1_dropShadow_4220_6128"
                        result="shape"
                    />
                </filter>
            </defs>
        </svg>
    );
}

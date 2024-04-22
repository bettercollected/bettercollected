import React, { SVGAttributes } from 'react';

export default function UserMoreIcon(props: SVGAttributes<{}>) {
    return (
        <svg
            width="48"
            height="48"
            viewBox="0 0 48 48"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M6 38H2V36C2 32.2723 4.54955 29.1401 8 28.252M12 21.6586C9.66962 20.8349 8 18.6125 8 16C8 13.3876 9.66962 11.1651 12 10.3414M42 38H46V36C46 32.2723 43.4505 29.1401 40 28.252M36 10.3414C38.3304 11.1651 40 13.3876 40 16C40 18.6125 38.3304 20.8349 36 21.6586M20 28H28C32.4183 28 36 31.5817 36 36V38H12V36C12 31.5817 15.5817 28 20 28ZM30 16C30 19.3137 27.3137 22 24 22C20.6863 22 18 19.3137 18 16C18 12.6863 20.6863 10 24 10C27.3137 10 30 12.6863 30 16Z"
                stroke="#343A40"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

import React from 'react';

const SaveIcon = (props: React.SVGAttributes<{}>) => {
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
                d="M15.375 21V15.375H8.625V21M18.75 21H5.25C4.00736 21 3 19.9926 3 18.75V5.25C3 4.00736 4.00736 3 5.25 3H14.443C15.0398 3 15.6121 3.23705 16.034 3.65901L20.341 7.96599C20.7629 8.38795 21 8.96024 21 9.55698V18.75C21 19.9926 19.9926 21 18.75 21Z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
};

export default SaveIcon;

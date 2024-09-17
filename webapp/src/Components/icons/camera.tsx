import React, { SVGAttributes } from 'react';

const Camera = (props: SVGAttributes<{}>) => {
    return (
        <svg width="25" height="24" viewBox="0 0 25 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path
                d="M21.5 17V9C21.5 7.89543 20.6046 7 19.5 7H17C16.4477 7 16 6.55228 16 6C16 5.44772 15.5523 5 15 5H10C9.44772 5 9 5.44772 9 6C9 6.55228 8.55228 7 8 7H5.5C4.39543 7 3.5 7.89543 3.5 9V17C3.5 18.1046 4.39543 19 5.5 19H19.5C20.6046 19 21.5 18.1046 21.5 17Z"
                stroke="currentColor"
                strokeWidth={props.strokeWidth || 2}
            />
            <path d="M15.5 13C15.5 14.6569 14.1569 16 12.5 16C10.8431 16 9.5 14.6569 9.5 13C9.5 11.3431 10.8431 10 12.5 10C14.1569 10 15.5 11.3431 15.5 13Z" stroke="currentColor" strokeWidth={props.strokeWidth || 2} />
        </svg>
    );
};

export default Camera;

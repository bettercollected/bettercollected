import React from 'react';

export const Copy: React.FC<React.SVGAttributes<{}>> = (props) => {
    return (
        <svg data-testid="copy-svg" width="12" height="12" viewBox="0 0 12 12" fill="none" {...props}>
            <path
                d="M4.00501 0C1.79311 0 0 1.79311 0 4.00501V8.95512C0 9.24363 0.233883 9.47751 0.522393 9.47751C0.810903 9.47751 1.04479 9.24363 1.04479 8.95512V4.00501C1.04479 2.37013 2.37013 1.04479 4.00501 1.04479H8.88964C9.17815 1.04479 9.41203 0.810903 9.41203 0.522393C9.41203 0.233883 9.17815 0 8.88964 0H4.00501Z"
                fill="currentColor"
            />
            <path
                d="M10.5541 2.46797C8.29672 2.21567 5.98205 2.21567 3.72465 2.46797C3.08156 2.53984 2.56479 3.04593 2.48899 3.694C2.22126 5.98311 2.22126 8.29563 2.48899 10.5847C2.56479 11.2328 3.08156 11.7389 3.72465 11.8108C5.98205 12.0631 8.29672 12.0631 10.5541 11.8108C11.1972 11.7389 11.714 11.2328 11.7898 10.5847C12.0575 8.29563 12.0575 5.98311 11.7898 3.694C11.714 3.04593 11.1972 2.53984 10.5541 2.46797ZM3.8407 3.50629C6.02097 3.26261 8.2578 3.26261 10.4381 3.50629C10.6034 3.52476 10.7334 3.65551 10.7521 3.81537C11.0104 6.02384 11.0104 8.2549 10.7521 10.4634C10.7334 10.6232 10.6034 10.754 10.4381 10.7725C8.2578 11.0161 6.02097 11.0161 3.8407 10.7725C3.67537 10.754 3.5454 10.6232 3.5267 10.4634C3.2684 8.2549 3.2684 6.02384 3.5267 3.81537C3.5454 3.65551 3.67537 3.52476 3.8407 3.50629Z"
                fill="currentColor"
            />
        </svg>
    );
};
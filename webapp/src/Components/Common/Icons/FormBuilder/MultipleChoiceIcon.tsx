import React from 'react';

export default function MultipleChoiceIcon(props: React.SVGAttributes<any>) {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <rect x="3" y="3" width="18" height="18" rx="9" stroke="#343A40" strokeWidth="2" />
            <rect x="8" y="8" width="8" height="8" rx="4" fill="#343A40" />
        </svg>
    );
}
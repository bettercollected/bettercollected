import React from 'react';

export default function DashboardIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <rect x="4" y="4" width="7" height="7" rx="1" stroke="#212529" strokeLinecap="round" />
            <rect x="4" y="13" width="7" height="7" rx="1" stroke="#212529" strokeLinecap="round" />
            <rect x="13" y="4" width="7" height="7" rx="1" stroke="#212529" strokeLinecap="round" />
            <rect x="13" y="13" width="7" height="7" rx="1" stroke="#212529" strokeLinecap="round" />
        </svg>
    );
}

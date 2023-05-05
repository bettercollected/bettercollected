import React from 'react';

export default function Eye({ props }: any) {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path d="M12 6C7.33385 6 3.38308 8.51733 2 12C3.38308 15.4827 7.33385 18 12 18C16.6662 18 20.6169 15.4827 22 12C20.6169 8.51733 16.6662 6 12 6Z" stroke="currentColor" strokeMiterlimit="10" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z" stroke="currentColor" strokeMiterlimit="10" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
}

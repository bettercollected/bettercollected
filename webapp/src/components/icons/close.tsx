import React from 'react';
import cn from "classnames";

export function Close(props: React.SVGAttributes<{}>) {
    const {className, ...otherProps} = props
    return (
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg"
             className={cn("cursor-pointer ", className)} {...otherProps}>
            <path d="M1 17L17 1" stroke="currentColor" strokeLinecap="round"/>
            <path d="M1 1L17 17" stroke="currentColor" strokeLinecap="round"/>
        </svg>
    );
}

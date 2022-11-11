import React from 'react';

import cn from 'classnames';
import { OverlayScrollbarsComponent, OverlayScrollbarsComponentProps } from 'overlayscrollbars-react';
import 'overlayscrollbars/css/OverlayScrollbars.css';

interface ScrollbarProps extends OverlayScrollbarsComponentProps {
    style?: React.CSSProperties;
    className?: string;
}

export default function Scrollbar({ options, style, className, ...props }: React.PropsWithChildren<ScrollbarProps>) {
    const autoHide: any = 'scroll';
    return (
        <OverlayScrollbarsComponent
            options={{
                className: cn('os-theme-thin', className),
                scrollbars: {
                    autoHide
                },
                ...options
            }}
            style={style}
            {...props}
        />
    );
}

import React from 'react';

import { Tooltip as MuiTooltip, PopperProps, SxProps, Theme } from '@mui/material';

interface ITooltipProps {
    title: string;
    children: React.ReactElement;
    className?: string;
    onClick?: any;
    components?: { Arrow?: any; Popper?: any; Tooltip?: any; Transition?: any };
    componentsProps?: { arrow?: object; popper?: object; tooltip?: object; transition?: object };
    arrow?: boolean;
    describeChild?: boolean;
    disableFocusListener?: boolean;
    disableHoverListener?: boolean;
    disableInteractive?: boolean;
    disableTouchListener?: boolean;
    enterDelay?: number;
    enterNextDelay?: number;
    enterTouchDelay?: number;
    followCursor?: boolean;
    leaveDelay?: number;
    leaveTouchDelay?: number;
    placement?: 'bottom' | 'bottom-end' | 'bottom-start' | 'left-end' | 'left-start' | 'left' | 'right-end' | 'right-start' | 'right' | 'top-end' | 'top-start' | 'top';
    PopperProps?: Partial<PopperProps>;
    slotProps?: { arrow?: object; popper?: object; tooltip?: object; transition?: object };
    slots?: { arrow?: any; popper?: any; tooltip?: any; transition?: any };
    sx?: SxProps<Theme>;
}

export default function Tooltip({
    title,
    children,
    components = {},
    className = '',
    onClick = () => {},
    componentsProps = {
        tooltip: {
            sx: {
                padding: '4px 12px',
                fontSize: '14px',
                lineHeight: '21px',
                color: '#F2F7FF',
                backgroundColor: '#343A40',
                opacity: '0.7 !important',
                borderRadius: '4px',
                '& .MuiTooltip-arrow': {
                    color: 'common.black',
                    opacity: '0.7 !important'
                }
            }
        }
    },
    arrow = false,
    describeChild = false,
    disableFocusListener = false,
    disableHoverListener = false,
    disableInteractive = false,
    disableTouchListener = false,
    enterDelay = 100,
    enterNextDelay = 0,
    enterTouchDelay = 100,
    followCursor = false,
    leaveDelay = 0,
    leaveTouchDelay = 100,
    placement = 'bottom',
    PopperProps = {},
    slotProps = {},
    slots = {},
    sx = {}
}: ITooltipProps) {
    return (
        <MuiTooltip
            title={title}
            sx={sx}
            className={className}
            onClick={onClick}
            components={components}
            componentsProps={componentsProps}
            arrow={arrow}
            describeChild={describeChild}
            disableFocusListener={disableFocusListener}
            disableHoverListener={disableHoverListener}
            disableInteractive={disableInteractive}
            disableTouchListener={disableTouchListener}
            enterDelay={enterDelay}
            enterNextDelay={enterNextDelay}
            enterTouchDelay={enterTouchDelay}
            followCursor={followCursor}
            leaveDelay={leaveDelay}
            leaveTouchDelay={leaveTouchDelay}
            placement={placement}
            PopperProps={PopperProps}
            slotProps={slotProps}
            slots={slots}
        >
            {children}
        </MuiTooltip>
    );
}

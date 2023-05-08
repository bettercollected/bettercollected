import { ElementType } from 'react';

import { DividerClasses, DividerPropsVariantOverrides, Divider as MuiDivider, SxProps, Theme } from '@mui/material';
import { OverridableStringUnion } from '@mui/types';

interface IDividerProps {
    className?: string;
    absolute?: boolean;
    children?: React.ReactNode;
    classes?: Partial<DividerClasses>;
    component?: ElementType<any>;
    flexItem?: boolean;
    light?: boolean;
    orientation?: 'vertical' | 'horizontal';
    sx?: SxProps<Theme>;
    textAlign?: 'center' | 'left' | 'right';
    variant?: OverridableStringUnion<'inset' | 'fullWidth' | 'middle', DividerPropsVariantOverrides>;
}

export default function Divider({
    className = 'text-black-400 border-black-400',
    absolute = false,
    children = null,
    classes = {},
    component = 'hr',
    flexItem = false,
    light = false,
    orientation = 'horizontal',
    sx = {},
    textAlign = 'center',
    variant = 'fullWidth'
}: IDividerProps) {
    return (
        <MuiDivider className={className} absolute={absolute} classes={classes} component={component} flexItem={flexItem} light={light} orientation={orientation} sx={sx} textAlign={textAlign} variant={variant}>
            {children}
        </MuiDivider>
    );
}

import React from 'react';

import { LoaderSizeTypes, LoaderVariantTypes } from '@app/components/ui/loader';

type ShapeNames = 'rounded' | 'pill' | 'circle';
type VariantNames = 'ghost' | 'solid' | 'transparent' | 'outline';
type ColorNames = 'primary' | 'white' | 'gray' | 'success' | 'info' | 'warning' | 'danger';
type SizeNames = 'large' | 'extraMedium' | 'medium' | 'small' | 'extraSmall';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    isLoading?: boolean;
    disabled?: boolean;
    shape?: ShapeNames;
    variant?: VariantNames;
    color?: ColorNames;
    size?: SizeNames;
    fullWidth?: boolean;
    loaderSize?: LoaderSizeTypes;
    loaderVariant?: LoaderVariantTypes;
    onClick?: React.MouseEventHandler<HTMLButtonElement>;
}

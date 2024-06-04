import React from 'react';

import { Avatar, SxProps, Theme } from '@mui/material';
import { AvatarPropsVariantOverrides } from '@mui/material/Avatar/Avatar';
import { OverridableStringUnion } from '@mui/types';
import cn from 'classnames';

interface IAuthAccountProfileImageProps {
    size?: number;
    image?: string;
    name: string;
    typography?: string;
    className?: string;
    style?: SxProps<Theme>;
    variant?: OverridableStringUnion<'circular' | 'rounded' | 'square', AvatarPropsVariantOverrides>;
}

AuthAccountProfileImage.defaultProps = {
    size: 36
};

export default function AuthAccountProfileImage({ size, image, name = ' ', className = '', typography = 'sh1', style = {}, variant = 'rounded' }: IAuthAccountProfileImageProps) {
    if (image) return <Avatar sx={{ width: size, height: size, borderRadius: 1, ...style }} variant={variant} src={image} className={`${variant === 'circular' ? '!rounded-full' : 'rounded'} !mr-0 overflow-hidden ${className}`} />;

    return (
        <Avatar sx={{ width: size, height: size, borderRadius: 1, ...style }} variant={variant} className={cn(`overflow-hidden rounded bg-green-500 ${className}`, variant === 'circular' && '!rounded-full')}>
            <span className={cn('font-semibold !text-white', typography)}>{name[0]?.toUpperCase()}</span>
        </Avatar>
    );
}

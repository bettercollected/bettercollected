import React from 'react';

import { Avatar, SxProps, Theme } from '@mui/material';
import cn from 'classnames';

interface IAuthAccountProfileImageProps {
    size?: number;
    image?: string;
    name: string;
    typography?: string;
    className?: string;
    style?: SxProps<Theme>;
}

AuthAccountProfileImage.defaultProps = {
    size: 36
};

export default function AuthAccountProfileImage({ size, image, name = ' ', className = '', typography = 'sh1', style = {} }: IAuthAccountProfileImageProps) {
    if (image) return <Avatar sx={{ width: size, height: size, borderRadius: 1, ...style }} variant="rounded" src={image} className={`rounded overflow-hidden !mr-0 ${className}`} />;

    return (
        <Avatar sx={{ width: size, height: size, borderRadius: 1, ...style }} variant="rounded" className={`rounded bg-brand-400 overflow-hidden ${className}`}>
            <span className={cn('!text-white', typography)}>{name[0]?.toUpperCase()}</span>
        </Avatar>
    );
}

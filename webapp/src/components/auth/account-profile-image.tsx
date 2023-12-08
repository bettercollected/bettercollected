import React from 'react';

import {Avatar, SxProps, Theme} from '@mui/material';
import {AvatarPropsVariantOverrides} from '@mui/material/Avatar/Avatar';
import {OverridableStringUnion} from '@mui/types';
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

export default function AuthAccountProfileImage({
                                                    size,
                                                    image,
                                                    name = ' ',
                                                    className = '',
                                                    typography = 'sh1',
                                                    style = {},
                                                    variant = 'rounded'
                                                }: IAuthAccountProfileImageProps) {
    if (image) return <Avatar sx={{width: size, height: size, ...style}} variant={variant} src={image}
                              className={` overflow-hidden !mr-0 ${className}`}/>;

    return (
        <Avatar sx={{width: size, height: size, ...style}} variant={variant}
                className={` bg-green-500 overflow-hidden ${className}`}>
            <span
                className={cn(`!text-white font-semibold `, typography)}>{name[0]?.toUpperCase()}</span>
        </Avatar>
    );
}
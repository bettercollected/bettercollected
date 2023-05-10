import { useState } from 'react';

import { Avatar } from '@mui/material';
import cn from 'classnames';

interface IAuthAccountProfileImageProps {
    size?: number;
    image?: string;
    name: string;
    typography?: string;
}

AuthAccountProfileImage.defaultProps = {
    size: 36
};

export default function AuthAccountProfileImage({ size, image, name = ' ', typography = 'sh1' }: IAuthAccountProfileImageProps) {
    if (image) return <Avatar sx={{ width: size, height: size, borderRadius: 1 }} variant="rounded" src={image} className="rounded overflow-hidden !mr-0" />;

    return (
        <Avatar sx={{ width: size, height: size, borderRadius: 1 }} variant="rounded" className="rounded !bg-brand-400 overflow-hidden">
            <span className={cn('!text-white', typography)}>{name[0]?.toUpperCase()}</span>
        </Avatar>
    );
}

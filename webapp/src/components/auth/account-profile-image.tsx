import React from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@app/shadcn/components/ui/avatar';
import { cn } from '@app/shadcn/util/lib';

interface IAuthAccountProfileImageProps {
    size?: number;
    image?: string;
    name?: string;
    typography?: string;
    className?: string;
    style?: any;
    variant?: 'circular' | 'rounded' | 'square';
}

export default function AuthAccountProfileImage({
    size = 36,
    image,
    name = ' ',
    className = '',
    typography = 'text-sm',
    style = {},
    variant = 'rounded'
}: IAuthAccountProfileImageProps) {

    // Map variant to Tailwind rounded classes
    const roundedClass = variant === 'circular' ? 'rounded-full' : variant === 'rounded' ? 'rounded-md' : 'rounded-none';

    return (
        <Avatar
            className={cn(roundedClass, "overflow-hidden", className)}
            style={{ width: size, height: size, ...style }}
        >
            <AvatarImage src={image} className="object-cover" />
            <AvatarFallback className={cn("bg-[#E9EFFC] text-[#2456CC] font-semibold flex items-center justify-center h-full w-full", roundedClass)}>
                <span className={cn(typography)}>{name?.[0]?.toUpperCase()}</span>
            </AvatarFallback>
        </Avatar>
    );
}

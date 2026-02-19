// @ts-nocheck
import React from 'react';
import { cn } from '@app/shadcn/util/lib';

interface IDividerProps {
    className?: string;
    orientation?: 'vertical' | 'horizontal';
    children?: React.ReactNode;
    textAlign?: 'center' | 'left' | 'right';
    style?: any;
    absolute?: boolean;
    flexItem?: boolean;
    light?: boolean;
    variant?: any;
    component?: any;
}

export default function Divider({ className, orientation = 'horizontal', children, textAlign = 'center', ...props }: IDividerProps) {
    if (orientation === 'vertical') {
        return <div className={cn("inline-flex h-full min-h-[1em] w-[1px] self-stretch bg-slate-200 mx-2", className)} {...props} />;
    }

    if (children) {
        return (
            <div className={cn("relative flex items-center w-full my-4", className)}>
                {textAlign !== 'left' && <div className="flex-grow border-t border-slate-200"></div>}
                <span className={cn("flex-shrink text-slate-500 text-xs font-semibold uppercase", textAlign === 'center' ? "mx-4" : textAlign === 'left' ? "mr-4" : "ml-4")}>
                    {children}
                </span>
                {textAlign !== 'right' && <div className="flex-grow border-t border-slate-200"></div>}
            </div>
        );
    }

    return <hr className={cn("shrink-0 bg-slate-200 h-[1px] w-full border-none my-2", className)} {...props} />;
}

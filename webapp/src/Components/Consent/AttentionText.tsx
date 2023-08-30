import React from 'react';

import cn from 'classnames';

import { OnlyClassNameInterface } from '@app/models/interfaces';

interface AttentionTextProps extends OnlyClassNameInterface {
    text: string;
}
export default function AttentionText({ text, className }: AttentionTextProps) {
    return <div className={cn('h5-new font-semibold leading-6 !text-new-pink', className)}>{text}</div>;
}

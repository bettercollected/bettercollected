import * as React from 'react';

import { cn } from '@app/shadcn/util/lib';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, ...props }, ref) => {
    return (
        <textarea
            style={{
                resize: 'none'
            }}
            className={cn(`w-full border-0 border-b-[1px] px-0 py-2 text-[32px] disabled:cursor-not-allowed disabled:opacity-50`, className)}
            ref={ref}
            {...props}
        />
    );
});
Textarea.displayName = 'Textarea';

export { Textarea };

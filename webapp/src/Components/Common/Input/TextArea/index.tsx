import * as React from 'react';

import { Textarea } from '@app/shadcn/components/ui/textarea';
import { cn } from '@app/shadcn/util/lib';

const TextArea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<'textarea'>>(({ className, ...props }, ref) => {
    return (
        <Textarea
            className={cn("w-full rounded-md border-black-300 p-3 text-black-800 placeholder:text-black-400 min-h-[80px]", className)}
            ref={ref}
            aria-label="text-area"
            {...props}
        />
    );
});

TextArea.displayName = 'TextArea';
export default TextArea;

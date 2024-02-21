import { Loader2 } from 'lucide-react';

import { cn } from '@app/shadcn/util/lib';

const Loader = ({ className }: { className?: string }) => {
    return (
        <Loader2
            className={cn('text-primary/60 my-28 h-16 w-16 animate-spin', className)}
        />
    );
};

export default Loader;

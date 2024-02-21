import {Loader2} from 'lucide-react';
import {cn} from "@app/shadcn/util/lib";

const Loader = ({className}: { className?: string }) => {
    return (
        <Loader2
            className={cn('my-28 h-16 w-16 text-primary/60 animate-spin', className)}
        />
    );
};

export default Loader;
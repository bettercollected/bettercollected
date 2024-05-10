import { cn } from '@app/shadcn/util/lib';

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
    return <div className={cn('bg-black-100 animate-pulse rounded-md', className)} {...props} />;
}

export { Skeleton };

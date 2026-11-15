import { cn } from '@app/shadcn/util/lib';

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
    return <div className={cn('bg-app-wash-strong animate-pulse rounded-md', className)} {...props} />;
}

export { Skeleton };

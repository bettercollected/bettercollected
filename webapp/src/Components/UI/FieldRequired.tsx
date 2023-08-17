import cn from 'classnames';

export function FieldRequired({ className }: { className: string }) {
    return <div className={cn('absolute z-[50] !text-red-500 text-xl font-bold', className)}>*</div>;
}

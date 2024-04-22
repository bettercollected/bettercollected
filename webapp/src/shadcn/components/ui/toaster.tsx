'use client';

import {
    Toast,
    ToastClose,
    ToastDescription,
    ToastProvider,
    ToastTitle,
    ToastViewport
} from '@app/shadcn/components/ui/toast';
import { useToast } from '@app/shadcn/components/ui/use-toast';

export function Toaster() {
    const { toasts } = useToast();

    return (
        <ToastProvider>
            {toasts.map(function ({
                id,
                title,
                description,
                action,
                duration,
                ...props
            }) {
                return (
                    <Toast key={id} {...props} duration={2000}>
                        <div className="grid gap-1">
                            {title && <ToastTitle>{title}</ToastTitle>}
                            {description && (
                                <ToastDescription>{description}</ToastDescription>
                            )}
                        </div>
                        {action}
                        <ToastClose />
                    </Toast>
                );
            })}
            <ToastViewport />
        </ToastProvider>
    );
}

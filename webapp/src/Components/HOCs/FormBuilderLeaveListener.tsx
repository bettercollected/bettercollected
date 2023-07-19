import React, { useEffect } from 'react';

import { useRouter } from 'next/router';

import { selectIsFormDirty } from '@app/store/form-builder/selectors';
import { useAppSelector } from '@app/store/hooks';

interface IFormBuilderLeaveListenerProps {
    children: React.ReactNode | React.ReactNode[];
}

export default function FormBuilderLeaveListener({ children }: IFormBuilderLeaveListenerProps) {
    const router = useRouter();

    const isFormDirty = useAppSelector(selectIsFormDirty);

    useEffect(() => {
        const handleBeforeUnload = (event: any) => {
            if (isFormDirty) {
                event.preventDefault();
                event.returnValue = ''; // This empty string will prompt the browser to show a confirmation dialog
            }
        };

        const handleBeforePopState = (state: any) => {
            if (isFormDirty && !window.confirm('Are you sure you want to leave? Your changes will not be saved.')) {
                router.events.emit('routeChangeError', state);
                throw "Abort route change by user's confirmation."; // Prevent navigation
            }
            return true; // Allow navigation
        };

        const handleError = (state: any) => {
            // Handle the route change error
            // You can customize this function to perform any necessary actions
            return null;
        };

        window.addEventListener('beforeunload', handleBeforeUnload);
        router.events.on('routeChangeStart', handleBeforePopState);
        router.events.on('routeChangeError', handleError);

        return () => {
            window.removeEventListener('beforeunload', handleBeforeUnload);
            router.events.off('routeChangeStart', handleBeforePopState);
            router.events.off('routeChangeError', handleError);
        };
    }, [isFormDirty, router]);

    return <>{children}</>;
}

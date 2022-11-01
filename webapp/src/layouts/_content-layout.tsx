import React from 'react';

interface ContentLayoutProps {
    className?: string;
}

export default function ContentLayout({ children, className = '' }: React.PropsWithChildren<ContentLayoutProps>) {
    return (
        <div className="flex min-h-screen flex-col bg-white dark:bg-dark">
            <main className={`mb-0 min-h-screen px-6 pt-24 sm:px-8 sm:pt-24 sm:pb-20 lg:px-12 xl:px-[59px] ${className}`}>{children}</main>
        </div>
    );
}

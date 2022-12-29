import React from 'react';

interface ContentLayoutProps {
    className?: string;
}

export default function ContentLayout({ children, className = '' }: React.PropsWithChildren<ContentLayoutProps>) {
    return (
        <div className="flex flex-col bg-white dark:bg-dark">
            <main className={`mb-0 pt-24 px-6 sm:px-8 lg:px-12 xl:px-[59px] ${className}`}>{children}</main>
        </div>
    );
}

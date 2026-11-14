import React from 'react';

/** Sign-in belongs to the creator app: it wears the app's colour theme (tailwind.css, "App theme scope"). */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
    return <div data-app-theme="daybreak">{children}</div>;
}

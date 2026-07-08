import Link from 'next/link';

import BetterCollectedLogo from '@Components/icons/bettercollected-logo';

/**
 * Branded 404. Renders inside the root layout, so Public Sans + the trust
 * palette (Design-Language.md) are available. Copy stays plain and honest —
 * no cute "oops", no dead-end.
 */
export default function NotFound() {
    return (
        <main className="flex min-h-screen w-full flex-col items-center justify-center gap-6 bg-white px-6 py-16 text-center">
            <BetterCollectedLogo className="h-[19px]" />

            <div className="flex flex-col items-center gap-3">
                <span className="text-brand-500 text-sm font-semibold uppercase tracking-wide">Error 404</span>
                <h1 className="text-black-900 text-2xl font-semibold sm:text-3xl">This page isn&apos;t here</h1>
                <p className="text-black-600 max-w-md text-sm leading-relaxed sm:text-base">
                    The page you&apos;re looking for may have been moved, renamed, or never existed. If you followed a link to a form, it may have been unpublished by its owner.
                </p>
            </div>

            <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
                <Link href="/" className="bg-brand-500 hover:bg-brand-600 rounded-md px-5 py-2.5 text-sm font-medium text-white transition-colors">
                    Back to home
                </Link>
            </div>
        </main>
    );
}

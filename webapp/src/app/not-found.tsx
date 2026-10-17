import Link from 'next/link';

import SiretoFooter from '@app/components/layout/sireto-footer';
import BetterCollectedLogo from '@Components/icons/bettercollected-logo';

/**
 * Branded 404. Renders inside the root layout, so Instrument Sans and the
 * DESIGN.md palette are available. Copy stays plain and honest — no cute
 * "oops", no dead-end.
 */
export default function NotFound() {
    return (
        <main className="flex min-h-screen w-full flex-col items-center justify-center gap-6 bg-white px-6 py-16 text-center">
            <BetterCollectedLogo className="h-[19px]" />

            <div className="flex flex-col items-center gap-3">
                <span className="text-black-600 font-mono text-[13px] font-medium">Error 404</span>
                <h1 className="text-black-900 tracking-title text-2xl font-semibold sm:text-3xl">This page isn&apos;t here</h1>
                <p className="text-body max-w-md text-base">
                    The page you&apos;re looking for may have been moved, renamed, or never existed. If you followed a link to a form, it may have been unpublished by its owner.
                </p>
            </div>

            <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
                <Link href="/" className="bg-action hover:bg-action-hover active:bg-action-pressed key-edge [--key-edge:var(--color-action-pressed)] rounded px-5 py-2.5 text-sm font-medium text-white transition-colors">
                    Back to home
                </Link>
            </div>

            <SiretoFooter className="mt-10" />
        </main>
    );
}

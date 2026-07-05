import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'No Internet Connection – BetterCollected',
    robots: { index: false }
};

export default function OfflinePage() {
    return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-white px-6 text-center dark:bg-neutral-950">
            {/* Icon */}
            <svg
                className="mb-8 h-24 w-24 text-neutral-300 dark:text-neutral-600"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
            >
                {/* Wifi base arc */}
                <path d="M5 12.55a11 11 0 0 1 14.08 0" />
                <path d="M1.42 9a16 16 0 0 1 21.16 0" />
                <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
                <circle cx="12" cy="20" r="1" fill="currentColor" stroke="none" />
                {/* Slash */}
                <line x1="2" y1="2" x2="22" y2="22" stroke="currentColor" strokeWidth="1.5" />
            </svg>

            <h1 className="mb-2 text-2xl font-semibold text-neutral-900 dark:text-white">
                No internet connection
            </h1>
            <p className="mb-8 max-w-sm text-sm text-neutral-500 dark:text-neutral-400">
                It looks like you&apos;re offline. Check your network connection and we&apos;ll
                automatically reload the page once you&apos;re back online.
            </p>

            {/* Inline client script – tiny, no framework needed here */}
            {/* eslint-disable-next-line @next/next/no-sync-scripts */}
            <script
                dangerouslySetInnerHTML={{
                    __html: `
(function () {
  var btn = document.getElementById('retry-btn');
  function tryReload() {
    fetch('/favicon.ico', { method: 'HEAD', cache: 'no-store' })
      .then(function () { window.location.reload(); })
      .catch(function () {});
  }
  if (btn) btn.addEventListener('click', tryReload);
  window.addEventListener('online', function () {
    setTimeout(tryReload, 500);
  });
})();
                `.trim()
                }}
            />

            <button
                id="retry-btn"
                className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 active:scale-95"
            >
                Try again
            </button>
        </div>
    );
}

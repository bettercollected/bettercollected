'use client';

import { useState } from 'react';

/**
 * A drawn signature's image from the server's short-lived link. The link is
 * a bearer address to a private file: it is never sent on as a referrer. When
 * it cannot be loaded (expired, or the file is gone) the text says so instead
 * of a broken image.
 */
export default function SignatureImage({ url, alt, unavailable, className, fallbackClassName }: { url: string; alt: string; unavailable: string; className?: string; fallbackClassName?: string }) {
    const [failed, setFailed] = useState<string | null>(null);
    if (failed === url) return <span className={fallbackClassName}>{unavailable}</span>;
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt={alt} referrerPolicy="no-referrer" onError={() => setFailed(url)} className={className} />;
}

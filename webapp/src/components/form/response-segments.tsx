'use client';

import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { cn } from '@app/shadcn/util/lib';

/**
 * Segmented control shared by /responses and /deletion-requests — deletion
 * requests are a view over the same submissions, not a separate destination,
 * so they live under the single "Responses" tab.
 */
export default function ResponseSegments() {
    const pathname = usePathname();
    const params = useParams();
    const form = useAppSelector(selectForm);

    const base = `/${params?.workspace_name}/dashboard/forms/${params?.form_id}`;
    const segments = [
        { label: 'All responses', count: form?.responses ?? 0, href: `${base}/responses`, active: !!pathname?.endsWith('/responses') },
        { label: 'Deletion requests', count: (form as any)?.deletionRequests ?? 0, href: `${base}/deletion-requests`, active: !!pathname?.endsWith('/deletion-requests') }
    ];

    return (
        <div className="border-black-300 mb-6 inline-flex rounded-lg border bg-white p-0.5">
            {segments.map((segment) => (
                <Link
                    key={segment.href}
                    href={segment.href}
                    aria-current={segment.active ? 'page' : undefined}
                    className={cn('flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm', segment.active ? 'bg-black-100 text-black-900 font-semibold' : 'text-black-600 hover:text-black-900 font-medium')}
                >
                    {segment.label}
                    <span className="bg-black-200 text-black-700 rounded-full px-1.5 py-0.5 text-xs font-medium tabular-nums">{segment.count}</span>
                </Link>
            ))}
        </div>
    );
}

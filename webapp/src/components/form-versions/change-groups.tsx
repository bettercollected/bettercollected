'use client';

import { useTranslation } from 'react-i18next';

import type { VersionChange } from '@app/store/workspaces/form-versions-api';
import { describeChange, groupChanges } from '@app/utils/version-changes';

/**
 * The coded changes of a form comparison as sentences in the viewer's language, grouped by scope (the form, pages,
 * questions). Shared by the Versions compare page and the copy-to-another-workspace review, so the two say it alike.
 * `heading` is the level of the group headings, for the page they sit on.
 */
export default function ChangeGroups({ entries, idPrefix = 'changes', heading: Heading = 'h3' }: { entries: VersionChange[]; idPrefix?: string; heading?: 'h3' | 'h4' | 'h5' }) {
    const { t } = useTranslation();
    return (
        <div className="flex flex-col gap-5">
            {groupChanges(entries).map((group) => (
                <section key={group.scope} aria-labelledby={`${idPrefix}-${group.scope}`} className="flex flex-col gap-2">
                    <Heading id={`${idPrefix}-${group.scope}`} className="text-xs font-semibold tracking-wide text-black-700 uppercase">
                        {t(`FORM_VERSIONS.COMPARE.SCOPE_${group.scope}`)}
                    </Heading>
                    <ul className="flex flex-col divide-y divide-black-300 rounded border border-black-300 bg-white">
                        {group.changes.map((change, index) => (
                            <li key={`${change.kind}-${change.ref ?? ''}-${index}`} className="px-4 py-2.5 text-sm break-words">
                                {describeChange(t, change)}
                            </li>
                        ))}
                    </ul>
                </section>
            ))}
        </div>
    );
}

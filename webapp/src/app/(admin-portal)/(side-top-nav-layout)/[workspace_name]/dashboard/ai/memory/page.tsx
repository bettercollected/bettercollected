'use client';

import { useTranslation } from 'react-i18next';

import AIMemorySection from '@app/components/account-settings/ai-memory-section';

/**
 * The AI memory page (plan §2.4) — the same living document that appears in
 * the builder's chat tab and account settings, as the Memory tab of the AI
 * section, for every member. Transparency is the contract: everything the assistant
 * remembers is listed here, deletable, and the user can add their own.
 */
export default function AIMemoryPage() {
    const { t } = useTranslation();
    return (
        <div className="flex w-full max-w-[760px] flex-col gap-6 pb-10">
            <p className="text-black-600 max-w-[62ch] text-sm leading-relaxed">
                {t('STAFF.AI_MEMORY.PAGE_INTRO')}
            </p>
            <AIMemorySection />
        </div>
    );
}

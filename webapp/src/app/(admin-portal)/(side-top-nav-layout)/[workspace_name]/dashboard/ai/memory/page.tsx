'use client';

import AIMemorySection from '@app/components/account-settings/ai-memory-section';

/**
 * The AI memory page (plan §2.4) — the same living document that appears in
 * the builder's chat tab and account settings, as the Memory tab of the AI
 * section, for every member. Transparency is the contract: everything the assistant
 * remembers is listed here, deletable, and the user can add their own.
 */
export default function AIMemoryPage() {
    return (
        <div className="flex w-full max-w-[760px] flex-col gap-6 pb-10">
            <p className="text-black-600 max-w-[62ch] text-sm leading-relaxed">
                While you build forms with the assistant, it picks up durable style preferences — and only those. Everything it remembers is listed below; nothing is stored that you can&apos;t see and delete here. These apply at the lowest priority: your request and
                your organization&apos;s AI profile always win.
            </p>
            <AIMemorySection />
        </div>
    );
}

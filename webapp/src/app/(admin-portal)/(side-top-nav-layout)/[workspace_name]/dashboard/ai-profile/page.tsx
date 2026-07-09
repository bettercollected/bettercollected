'use client';

import { useEffect, useState } from 'react';

import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetAIProfileQuery, useUpdateAIProfileMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

const MAX_SECTION_CHARS = 8000;

const SECTIONS: Array<{ key: 'about' | 'guidelines' | 'compliance'; label: string; hint: string; placeholder: string }> = [
    {
        key: 'about',
        label: 'About your organization',
        hint: 'Tone of voice, audience, languages, vocabulary — how your forms should sound.',
        placeholder: 'e.g. We are a healthcare co-op. Warm but professional tone. Always write in British English. Our members are 50+, avoid jargon.'
    },
    {
        key: 'guidelines',
        label: 'Form guidelines',
        hint: 'Dos and don’ts the AI follows when it designs forms for this workspace.',
        placeholder: 'e.g. Never ask for exact age — use age ranges. NPS is always 0–10. Keep pages under 5 questions.'
    },
    {
        key: 'compliance',
        label: 'Compliance requirements',
        hint: 'Hard requirements. The AI will not violate these — even if a prompt asks it to.',
        placeholder: 'e.g. Every form collecting personal data must state its purpose and a retention period. Consent is always opt-in, never pre-ticked.'
    }
];

export default function AIProfilePage() {
    const workspace = useAppSelector(selectWorkspace);
    const isAdmin = useAppSelector(selectIsAdmin);
    const { toast } = useToast();

    const { data, isLoading } = useGetAIProfileQuery(workspace?.id, { skip: !workspace?.id });
    const [updateProfile, { isLoading: isSaving }] = useUpdateAIProfileMutation();

    const [draft, setDraft] = useState({ about: '', guidelines: '', compliance: '' });
    const [dirty, setDirty] = useState(false);

    useEffect(() => {
        if (data && !dirty) {
            setDraft({ about: data.about ?? '', guidelines: data.guidelines ?? '', compliance: data.compliance ?? '' });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [data]);

    const handleSave = async () => {
        const response: any = await updateProfile({ workspace_id: workspace.id, body: draft });
        if (response.data) {
            setDirty(false);
            toast({ description: 'AI profile saved' });
        } else {
            toast({ description: 'Could not save the AI profile. Please try again.', variant: 'destructive' });
        }
    };

    return (
        <div className="flex w-full max-w-[760px] flex-col gap-8 px-5 py-6 lg:px-10">
            <div className="flex flex-col gap-1.5">
                <p className="text-black-600 max-w-[62ch] text-sm leading-relaxed">
                    Everything here is given to the AI whenever it creates or edits a form in this workspace. It’s a plain document you own — what you see below is exactly what the AI is told, nothing hidden.
                </p>
            </div>

            {SECTIONS.map((section) => (
                <div key={section.key} className="flex flex-col gap-2">
                    <div className="flex items-baseline justify-between gap-3">
                        <label htmlFor={`ai-profile-${section.key}`} className="text-black-900 text-sm font-semibold">
                            {section.label}
                        </label>
                        <span className="text-black-500 shrink-0 text-xs tabular-nums">
                            {draft[section.key].length.toLocaleString()} / {MAX_SECTION_CHARS.toLocaleString()}
                        </span>
                    </div>
                    <p className="text-black-600 text-xs leading-relaxed">{section.hint}</p>
                    <textarea
                        id={`ai-profile-${section.key}`}
                        rows={6}
                        maxLength={MAX_SECTION_CHARS}
                        value={draft[section.key]}
                        placeholder={section.placeholder}
                        disabled={!isAdmin || isLoading}
                        onChange={(e) => {
                            setDraft({ ...draft, [section.key]: e.target.value });
                            setDirty(true);
                        }}
                        className="border-black-300 text-black-900 placeholder:text-black-400 focus:border-brand-500 w-full resize-y rounded-md border bg-white px-3.5 py-3 text-sm leading-relaxed outline-none transition duration-150 focus:shadow-[0_0_0_3px_rgba(36,86,204,0.15)] disabled:cursor-not-allowed disabled:opacity-60"
                    />
                </div>
            ))}

            {isAdmin ? (
                <div className="flex items-center gap-4">
                    <Button size="medium" variant="primary" isLoading={isSaving} disabled={!dirty} onClick={handleSave}>
                        Save profile
                    </Button>
                    {dirty && <span className="text-black-500 text-xs">Unsaved changes</span>}
                </div>
            ) : (
                <p className="text-black-500 text-xs">Only workspace admins can edit the AI profile.</p>
            )}
        </div>
    );
}

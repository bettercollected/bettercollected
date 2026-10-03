'use client';

import { useState } from 'react';

import { Plus, X } from 'lucide-react';

import { Button } from '@app/shadcn/components/ui/button';
import { AppInput } from '@app/shadcn/components/ui/input';
import { DEFAULT_FEEDBACK_STATUSES, MAX_FEEDBACK_STATUSES, MAX_FEEDBACK_STATUS_LENGTH, validateFeedbackStatuses } from '@app/utils/respondent-feedback';

interface FeedbackStatusesEditorProps {
    statuses?: string[];
    onSave: (statuses: string[]) => Promise<unknown> | void;
}

/**
 * The statuses the team can give a submission ("Under review", "Selected",
 * ...), edited as a short list and saved at once. Checked here with the
 * backend's rules so a bad list never leaves the page.
 */
export default function FeedbackStatusesEditor({ statuses, onSave }: FeedbackStatusesEditorProps) {
    const initial = statuses ?? DEFAULT_FEEDBACK_STATUSES;
    const [items, setItems] = useState<string[]>(initial);
    const [saving, setSaving] = useState(false);

    const { statuses: cleaned, error } = validateFeedbackStatuses(items);
    const changed = cleaned.length !== initial.length || cleaned.some((status, index) => status !== initial[index]);

    const save = async () => {
        setSaving(true);
        try {
            await onSave(cleaned);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="flex flex-col gap-2 pt-3" aria-label="Submission statuses">
            {items.map((item, index) => (
                <div key={index} className="flex items-center gap-2">
                    <AppInput
                        aria-label={`Status ${index + 1}`}
                        className="w-full max-w-[320px] !text-sm"
                        maxLength={MAX_FEEDBACK_STATUS_LENGTH}
                        value={item}
                        onChange={(e) => setItems((prev) => prev.map((value, i) => (i === index ? e.target.value : value)))}
                    />
                    <button type="button" aria-label={`Remove ${item || `status ${index + 1}`}`} className="rounded p-1 text-black-500 hover:text-black-800" onClick={() => setItems((prev) => prev.filter((_, i) => i !== index))}>
                        <X className="h-4 w-4" />
                    </button>
                </div>
            ))}
            {error && <span className="text-xs text-[#C43D3D]">{error}</span>}
            <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" icon={<Plus className="h-4 w-4" />} disabled={items.length >= MAX_FEEDBACK_STATUSES} onClick={() => setItems((prev) => [...prev, ''])}>
                    Add status
                </Button>
                <Button variant="secondary" size="sm" isLoading={saving} disabled={!changed || !!error || saving} onClick={save}>
                    Save statuses
                </Button>
            </div>
        </div>
    );
}

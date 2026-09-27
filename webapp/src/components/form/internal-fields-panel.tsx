'use client';

import { useState } from 'react';

import { Lock } from 'lucide-react';

import { AnswerDto, FieldTypes, InternalAnswerMeta, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { AppInput } from '@app/shadcn/components/ui/input';
import { Textarea } from '@app/shadcn/components/ui/textarea';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useUpdateInternalAnswersMutation } from '@app/store/workspaces/api';
import { utcToLocalDateTIme } from '@app/utils/date-utils';
import { buildInternalAnswer, InternalInputValue, internalAnswerChanged, internalAnswerToInput } from '@app/utils/internal-fields';
import { fieldText, selectClass } from '@app/views/molecules/form-builder/condition-editor-shared';

interface InternalFieldsPanelProps {
    fields: StandardFormFieldDto[];
    response: StandardFormResponseDto;
    formId: string;
    workspaceId: string;
}

const inputClass = 'w-full !text-sm';

function InternalFieldInput({ field, value, onChange }: { field: StandardFormFieldDto; value: InternalInputValue; onChange: (value: InternalInputValue) => void }) {
    const id = `internal-${field.id}`;
    const choices = field.properties?.choices ?? [];
    switch (field.type) {
        case FieldTypes.LONG_TEXT:
            return <Textarea id={id} className="min-h-[72px] text-sm" value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} />;
        case FieldTypes.NUMBER:
            return <AppInput id={id} className={inputClass} type="number" step="1" value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} />;
        case FieldTypes.DATE:
            return <AppInput id={id} className={inputClass} type="date" value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} />;
        case FieldTypes.EMAIL:
            return <AppInput id={id} className={inputClass} type="email" value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} />;
        case FieldTypes.LINK:
            return <AppInput id={id} className={inputClass} type="url" value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} />;
        case FieldTypes.PHONE_NUMBER:
            return <AppInput id={id} className={inputClass} type="tel" value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} />;
        case FieldTypes.YES_NO:
            return (
                <select id={id} className={selectClass} value={value === true ? 'yes' : value === false ? 'no' : ''} onChange={(e) => onChange(e.target.value === '' ? undefined : e.target.value === 'yes')}>
                    <option value="">—</option>
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                </select>
            );
        case FieldTypes.MULTIPLE_CHOICE:
        case FieldTypes.DROP_DOWN:
            if (field.properties?.allowMultipleSelection) {
                const selected = Array.isArray(value) ? value : [];
                return (
                    <div id={id} role="group" className="flex flex-col gap-1.5">
                        {choices.map((choice, idx) => (
                            <label key={choice.id} className="text-black-800 flex cursor-pointer items-center gap-2 text-sm">
                                <input
                                    type="checkbox"
                                    className="h-4 w-4"
                                    checked={selected.includes(choice.id)}
                                    onChange={(e) => onChange(e.target.checked ? [...selected, choice.id] : selected.filter((c) => c !== choice.id))}
                                />
                                {choice.value || `Item ${idx + 1}`}
                            </label>
                        ))}
                    </div>
                );
            }
            return (
                <select id={id} className={selectClass} value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)}>
                    <option value="">—</option>
                    {choices.map((choice, idx) => (
                        <option key={choice.id} value={choice.id}>
                            {choice.value || `Item ${idx + 1}`}
                        </option>
                    ))}
                </select>
            );
        default:
            return <AppInput id={id} className={inputClass} value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} />;
    }
}

/**
 * The "office use" section of a submission: the form's internal fields, which
 * respondents never see, filled in and edited by the team. Each field shows
 * who changed it last. Only rendered in the dashboard (workspace members).
 */
export default function InternalFieldsPanel({ fields, response, formId, workspaceId }: InternalFieldsPanelProps) {
    const { toast } = useToast();
    const [updateInternalAnswers, { isLoading }] = useUpdateInternalAnswersMutation();

    const [stored, setStored] = useState<Record<string, AnswerDto>>(response?.internalAnswers ?? {});
    const [meta, setMeta] = useState<Record<string, InternalAnswerMeta>>(response?.internalAnswersMeta ?? {});
    const toInputs = (answers: Record<string, AnswerDto>) => Object.fromEntries(fields.map((f) => [f.id, internalAnswerToInput(f, answers[f.id])]));
    // Initialised once per mounted submission (the parent keys this panel by
    // response id); re-synced from the server's reply after each save.
    const [values, setValues] = useState<Record<string, InternalInputValue>>(() => toInputs(stored));

    if (!fields.length) return null;

    const changedFields = fields.filter((f) => internalAnswerChanged(f, stored[f.id], values[f.id]));
    const missingRequired = fields.filter((f) => f.validations?.required && buildInternalAnswer(f, values[f.id]) === null);

    const save = async () => {
        const answers = Object.fromEntries(changedFields.map((f) => [f.id, buildInternalAnswer(f, values[f.id])]));
        const result: any = await updateInternalAnswers({ workspaceId, formId, responseId: response.responseId, answers });
        if (result?.data) {
            const saved = result.data.internalAnswers ?? {};
            setStored(saved);
            setValues(toInputs(saved));
            setMeta(result.data.internalAnswersMeta ?? {});
            toast({ description: 'Internal fields saved' });
        } else {
            const detail = result?.error?.data;
            toast({ description: typeof detail === 'string' && detail ? detail : 'Could not save the internal fields', variant: 'destructive' });
        }
    };

    return (
        <section aria-labelledby="internal-fields-heading" className="border-black-200 bg-black-100 flex flex-col gap-4 rounded-lg border p-4">
            <div className="flex flex-col gap-0.5">
                <span id="internal-fields-heading" className="text-black-800 flex items-center gap-1.5 text-sm font-semibold">
                    <Lock className="h-3.5 w-3.5" aria-hidden="true" />
                    Internal · staff only
                </span>
                <span className="text-black-600 text-xs">Respondents never see these fields or their values.</span>
            </div>
            {fields.map((field) => {
                const fieldMeta = meta[field.id];
                return (
                    <div key={field.id} className="flex flex-col gap-1.5">
                        <label htmlFor={`internal-${field.id}`} className="text-black-700 text-[13px] font-medium leading-snug">
                            {fieldText(field)}
                            {field.validations?.required && (
                                <span className="text-black-500 ml-1 text-[11px] font-normal" title="Required for your team, not for respondents">
                                    (required)
                                </span>
                            )}
                        </label>
                        <InternalFieldInput field={field} value={values[field.id]} onChange={(value) => setValues((prev) => ({ ...prev, [field.id]: value }))} />
                        {fieldMeta?.updated_at && (
                            <span className="text-black-500 text-[11px]">
                                Last changed by {fieldMeta.updated_by_email || 'a team member'} · {utcToLocalDateTIme(fieldMeta.updated_at)}
                            </span>
                        )}
                    </div>
                );
            })}
            <div className="flex items-center justify-between gap-2">
                <span className="text-black-500 text-[11px]">{missingRequired.length > 0 ? `${missingRequired.length} required field${missingRequired.length > 1 ? 's' : ''} still empty` : ''}</span>
                <Button variant="primary" size="sm" isLoading={isLoading} disabled={changedFields.length === 0 || isLoading} onClick={save}>
                    Save
                </Button>
            </div>
        </section>
    );
}

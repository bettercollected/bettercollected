'use client';

import { useId, useRef, useState } from 'react';

import { ImageIcon } from 'lucide-react';

import { Button } from '@app/shadcn/components/ui/button';
import { Switch } from '@app/shadcn/components/ui/switch';
import { cn } from '@app/shadcn/util/lib';
import { selectForm, setFormLogo } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useRemoveFormLogoMutation, useUploadFormLogoMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { workspaceDisplayName } from '@app/utils/workspace-display-name';
import { LOGO_ACCEPT, LOGO_ALT_MAX_LENGTH, LogoPositionSetting, logoFileProblem, logoPositionFor, logoUploadError, resolveFormLogo } from '@app/utils/form-logo';

const POSITIONS: Array<{ key: LogoPositionSetting; label: string }> = [
    { key: 'auto', label: 'Automatic' },
    { key: 'left', label: 'Left' },
    { key: 'center', label: 'Centre' }
];

/**
 * The builder's "Organisation logo" settings (Design tab): upload, replace or
 * remove the logo, where it sits, its alt text, and whether a form without
 * one shows the workspace's logo. The file is stored at once; the settings
 * save with the form. Respondents see changes once the form is published.
 */
export default function FormLogoSettings() {
    const dispatch = useAppDispatch();
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { formState, setLogoSettings } = useFormState();
    const [uploadLogo, { isLoading: uploading }] = useUploadFormLogoMutation();
    const [removeLogo, { isLoading: removing }] = useRemoveFormLogoMutation();
    const [error, setError] = useState<string | null>(null);
    const fileRef = useRef<HTMLInputElement>(null);
    const ids = { alt: useId(), altHint: useId(), toggle: useId(), status: useId() };

    // Unset is Automatic: the logo follows the welcome page's alignment.
    const position: LogoPositionSetting = formState.logoPosition ?? form?.logoPosition ?? 'auto';
    const alt = formState.logoAlt ?? form?.logoAlt ?? '';
    const useWorkspaceLogo = formState.useWorkspaceLogo ?? form?.useWorkspaceLogo ?? false;
    const organisation = workspaceDisplayName(workspace) ?? '';
    const settings = { logoPosition: position, logoAlt: alt, useWorkspaceLogo };
    const followed = logoPositionFor({ welcomePage: formState.welcomePage, theme: formState.theme });
    const shown = resolveFormLogo({ logo: form?.logo, ...settings, welcomePage: formState.welcomePage, theme: formState.theme }, workspace);

    const pick = async (file?: File) => {
        if (fileRef.current) fileRef.current.value = '';
        if (!file || !workspace?.id || !form?.formId) return;
        const problem = logoFileProblem(file);
        if (problem) {
            setError(problem);
            return;
        }
        setError(null);
        const reply: any = await uploadLogo({ workspaceId: workspace.id, formId: form.formId, file });
        if (reply?.data) dispatch(setFormLogo(reply.data.logo));
        else setError(logoUploadError(reply?.error?.status, reply?.error?.data));
    };

    const remove = async () => {
        if (!workspace?.id || !form?.formId) return;
        setError(null);
        const reply: any = await removeLogo({ workspaceId: workspace.id, formId: form.formId });
        if (reply?.data) dispatch(setFormLogo(null));
        else setError('The logo could not be removed. Try again.');
    };

    return (
        <section aria-labelledby="form-logo-heading" className="flex flex-col gap-3">
            <div>
                <h3 id="form-logo-heading" className="text-xs font-semibold tracking-wide text-black-600 uppercase">
                    Organisation logo
                </h3>
                <p className="mt-1 text-xs leading-relaxed text-black-600">Shown at the top of every page of the form, as you upload it.</p>
            </div>

            {/* What respondents will see, on the form's own page colour. */}
            <div
                className="flex h-20 items-center rounded-md border border-black-300 px-3"
                style={{ background: formState.theme?.style === 'leaflet' ? '#FFFFFF' : formState.theme?.accent || '#FFFFFF', justifyContent: shown?.position === 'center' ? 'center' : 'flex-start' }}
                data-testid="form-logo-preview"
            >
                {shown ? (
                    // eslint-disable-next-line @next/next/no-img-element -- our own storage, shown as is
                    <img src={shown.src} alt={shown.alt} className="block h-auto max-h-12 w-auto max-w-[200px] object-contain" referrerPolicy="no-referrer" />
                ) : (
                    <span className="flex items-center gap-2 text-xs text-black-600">
                        <ImageIcon className="h-4 w-4" aria-hidden="true" />
                        No logo
                    </span>
                )}
            </div>
            {shown?.fromWorkspace && <p className="-mt-1 text-[11px] text-black-600">Showing the workspace logo.</p>}

            <input ref={fileRef} type="file" accept={LOGO_ACCEPT} className="sr-only" tabIndex={-1} aria-hidden="true" onChange={(event) => pick(event.target.files?.[0])} />
            <div className="flex items-center gap-2">
                <Button type="button" variant="v2Button" className="h-9 text-xs" disabled={removing} isLoading={uploading} onClick={() => fileRef.current?.click()} aria-describedby={ids.status}>
                    {form?.logo ? 'Replace' : 'Upload logo'}
                </Button>
                {form?.logo && (
                    <Button type="button" variant="v2GhostButton" className="h-9" disabled={uploading} isLoading={removing} onClick={remove}>
                        Remove
                    </Button>
                )}
            </div>
            <p id={ids.status} className={cn('text-[11px] leading-relaxed', error ? 'text-[#C43D3D]' : 'text-black-600')} role={error ? 'alert' : undefined}>
                {error ?? 'PNG, JPEG or WebP, up to 1 MB. Respondents see a new logo once you publish.'}
            </p>

            <div className="flex flex-col gap-2">
                <span className="text-xs text-black-700" id={`${ids.status}-position`}>
                    Position
                </span>
                <div className="flex overflow-hidden rounded-md border border-black-300" role="group" aria-labelledby={`${ids.status}-position`}>
                    {POSITIONS.map((option) => (
                        <button
                            key={option.key}
                            type="button"
                            aria-pressed={position === option.key}
                            onClick={() => setLogoSettings({ ...settings, logoPosition: option.key })}
                            className={cn('flex-1 px-2 py-1.5 text-[11px] font-medium transition-colors', position === option.key ? 'bg-brand-100 text-brand-600' : 'bg-white text-black-600 hover:bg-black-100')}
                        >
                            {option.label}
                        </button>
                    ))}
                </div>
                <p className="text-[11px] leading-relaxed text-black-600">
                    {position === 'auto'
                        ? `Automatic follows the welcome page: ${followed === 'center' ? 'it is centred, so the logo is centred on every page' : 'it is left-aligned, so the logo sits on the left on every page'}.`
                        : 'Used on every page of the form.'}
                </p>
            </div>

            <div className="flex flex-col gap-1.5">
                <label htmlFor={ids.alt} className="text-xs text-black-700">
                    Alt text
                </label>
                <input
                    id={ids.alt}
                    type="text"
                    value={alt}
                    maxLength={LOGO_ALT_MAX_LENGTH}
                    placeholder={organisation}
                    aria-describedby={ids.altHint}
                    onChange={(event) => setLogoSettings({ ...settings, logoAlt: event.target.value })}
                    className="h-9 w-full rounded-md border border-control bg-white px-2.5 text-xs text-black-900 placeholder:text-black-600"
                />
                <p id={ids.altHint} className="text-[11px] leading-relaxed text-black-600">
                    Read out instead of the image, usually the organisation&apos;s name.{organisation ? ` Leave empty to use “${organisation}”.` : ''}
                </p>
            </div>

            <div className="flex items-start justify-between gap-3">
                <label htmlFor={ids.toggle} className="text-xs leading-relaxed text-black-700">
                    Use workspace logo when the form has none
                </label>
                <Switch id={ids.toggle} checked={useWorkspaceLogo} onCheckedChange={(checked) => setLogoSettings({ ...settings, useWorkspaceLogo: checked })} className="mt-0.5" />
            </div>
        </section>
    );
}

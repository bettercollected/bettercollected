'use client';

import { useState } from 'react';

import { Pencil, Plus, Trash2 } from 'lucide-react';

import { FormTheme, ThemeColors } from '@app/constants/theme';
import { useModal } from '@app/components/modal-views/context';
import { AppInput } from '@app/shadcn/components/ui/input';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchWorkspaceThemesMutation } from '@app/store/workspaces/api';
import { selectWorkspace, setWorkspace } from '@app/store/workspaces/slice';
import { ContrastNotes, THEME_ROLE_FIELDS, ThemeBackgroundEditor, ThemePreview } from '@app/views/molecules/theme/theme-shared';

type Editing = { index: number | 'new'; draft: FormTheme } | null;

const NEW_THEME_SEED: Omit<FormTheme, 'title'> = {
    primary: ThemeColors[0].primary,
    secondary: ThemeColors[0].secondary,
    tertiary: ThemeColors[0].tertiary,
    accent: ThemeColors[0].accent
};

export default function ThemesPage() {
    const workspace = useAppSelector(selectWorkspace);
    const isAdmin = useAppSelector(selectIsAdmin);
    const dispatch = useAppDispatch();
    const { toast } = useToast();
    const { openModal } = useModal();
    const [patchWorkspaceThemes, { isLoading }] = usePatchWorkspaceThemesMutation();

    const savedThemes: FormTheme[] = workspace?.customThemes ?? [];
    const [editing, setEditing] = useState<Editing>(null);
    const [nameError, setNameError] = useState('');

    const saveThemes = async (nextList: FormTheme[], successMessage: string) => {
        const response: any = await patchWorkspaceThemes({ workspace_id: workspace.id, body: nextList });
        if (response.data) {
            dispatch(setWorkspace(response.data));
            toast({ description: successMessage });
            return true;
        }
        toast({ description: 'Could not save your themes. Please try again.', variant: 'destructive' });
        return false;
    };

    const handleSaveDraft = async () => {
        if (!editing) return;
        const name = editing.draft.title.trim();
        if (!name) {
            setNameError('Give this theme a name.');
            return;
        }
        const clash = savedThemes.some((theme, idx) => idx !== editing.index && theme.title.trim().toLowerCase() === name.toLowerCase());
        if (clash) {
            setNameError('You already have a theme with this name.');
            return;
        }
        const draft = { ...editing.draft, title: name };
        const nextList = editing.index === 'new' ? [...savedThemes, draft] : savedThemes.map((theme, idx) => (idx === editing.index ? draft : theme));
        if (await saveThemes(nextList, editing.index === 'new' ? 'Theme saved' : 'Theme updated')) {
            setEditing(null);
            setNameError('');
        }
    };

    const handleDelete = (index: number) => {
        openModal('DELETE_CONFIRMATION', {
            headerTitle: 'Delete theme',
            positiveText: 'Delete',
            title: 'Delete ' + savedThemes[index].title,
            handleDelete: () => {
                // Colours are stored inline on each form, so deleting a saved
                // theme never changes an already-styled form.
                saveThemes(
                    savedThemes.filter((_, idx) => idx !== index),
                    'Theme deleted'
                );
            }
        });
    };

    return (
        <div className="flex w-full max-w-[1200px] flex-col gap-10 px-5 py-6 lg:px-10">
            <p className="text-black-600 max-w-[62ch] text-sm leading-relaxed">
                Palettes for your forms. Save your own to reuse brand colours across the workspace, or start from a preset — apply either from the <span className="text-black-800 font-medium">Design</span> tab in the form builder.
            </p>

            {isAdmin && (
                <section className="flex flex-col gap-4">
                    <div className="flex flex-col gap-1">
                        <h2 className="text-black-900 text-base font-semibold">Your themes</h2>
                        <p className="text-black-600 text-sm">Saved for everyone in this workspace. Deleting one never changes forms already using it.</p>
                    </div>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                        {savedThemes.map((theme, index) => (
                            <div key={theme.title} className="border-black-300 group flex flex-col overflow-hidden rounded-lg border bg-white">
                                <ThemePreview color={theme} />
                                <div className="border-t-black-200 flex items-center justify-between border-t px-3 py-2">
                                    <span className="text-black-800 truncate text-xs font-medium">{theme.title}</span>
                                    <span className="flex shrink-0 items-center gap-1">
                                        <button
                                            type="button"
                                            aria-label={`Edit ${theme.title}`}
                                            onClick={() => {
                                                setNameError('');
                                                setEditing({ index, draft: { ...theme } });
                                            }}
                                            className="text-black-500 hover:bg-black-100 hover:text-black-800 rounded p-1.5 transition-colors"
                                        >
                                            <Pencil className="h-3.5 w-3.5" />
                                        </button>
                                        <button type="button" aria-label={`Delete ${theme.title}`} onClick={() => handleDelete(index)} className="text-black-500 rounded p-1.5 transition-colors hover:bg-[#FBEFEF] hover:text-[#C43D3D]">
                                            <Trash2 className="h-3.5 w-3.5" />
                                        </button>
                                    </span>
                                </div>
                            </div>
                        ))}

                        <button
                            type="button"
                            onClick={() => {
                                setNameError('');
                                setEditing({ index: 'new', draft: { title: '', ...NEW_THEME_SEED } });
                            }}
                            className="border-black-300 text-black-600 hover:border-brand-400 hover:text-brand-600 flex min-h-[120px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-white text-sm font-medium transition-colors"
                        >
                            <Plus className="h-5 w-5" />
                            New theme
                        </button>
                    </div>

                    {editing && (
                        <div className="border-black-300 flex max-w-[540px] flex-col gap-5 rounded-lg border bg-white p-5">
                            <h3 className="text-black-900 text-sm font-semibold">{editing.index === 'new' ? 'New theme' : `Edit ${savedThemes[editing.index as number]?.title}`}</h3>

                            <div className="flex flex-col gap-2">
                                <label htmlFor="theme-name" className="text-black-700 text-sm font-medium">
                                    Name
                                </label>
                                <AppInput
                                    id="theme-name"
                                    value={editing.draft.title}
                                    placeholder="e.g. Acme brand"
                                    className={`!text-sm ${nameError ? '!border-[#C43D3D]' : ''}`}
                                    onChange={(e) => {
                                        setNameError('');
                                        setEditing({ ...editing, draft: { ...editing.draft, title: e.target.value } });
                                    }}
                                />
                                {nameError && <p className="text-sm text-[#C43D3D]">{nameError}</p>}
                            </div>

                            <div className="flex flex-col gap-2.5">
                                {THEME_ROLE_FIELDS.map((field) => (
                                    <div key={field.key} className="flex items-center justify-between gap-3">
                                        <span className="text-black-700 text-sm">{field.label}</span>
                                        <span className="flex items-center gap-2">
                                            <span className="text-black-500 text-xs uppercase tabular-nums">{editing.draft[field.key]}</span>
                                            <input
                                                type="color"
                                                aria-label={field.label}
                                                value={editing.draft[field.key]}
                                                onChange={(e) => setEditing({ ...editing, draft: { ...editing.draft, [field.key]: e.target.value } })}
                                                className="border-black-300 h-8 w-10 cursor-pointer rounded border bg-white p-0.5"
                                            />
                                        </span>
                                    </div>
                                ))}
                            </div>

                            <ThemeBackgroundEditor theme={editing.draft} onChange={(background) => setEditing({ ...editing, draft: { ...editing.draft, background } })} />

                            <div className="rounded-lg">
                                <div className="text-black-600 mb-1.5 text-xs font-medium uppercase tracking-wide">Preview</div>
                                <div className="border-black-200 overflow-hidden rounded-lg border">
                                    <ThemePreview color={editing.draft} />
                                </div>
                                <ContrastNotes theme={editing.draft} />
                            </div>

                            <div className="flex items-center gap-3">
                                <Button size="sm" variant="primary" isLoading={isLoading} onClick={handleSaveDraft}>
                                    {editing.index === 'new' ? 'Save theme' : 'Save changes'}
                                </Button>
                                <Button
                                    size="sm"
                                    variant="v2Button"
                                    onClick={() => {
                                        setEditing(null);
                                        setNameError('');
                                    }}
                                >
                                    Cancel
                                </Button>
                            </div>
                        </div>
                    )}
                </section>
            )}

            <section className="flex flex-col gap-4">
                <div className="flex flex-col gap-1">
                    <h2 className="text-black-900 text-base font-semibold">Presets</h2>
                    <p className="text-black-600 text-sm">Ready-made palettes. Every preset meets WCAG AA contrast for questions, buttons and inputs.</p>
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {ThemeColors.map((theme) => (
                        <div key={theme.title} className="border-black-300 flex flex-col overflow-hidden rounded-lg border bg-white">
                            <ThemePreview color={theme} />
                            <div className="border-t-black-200 border-t px-3 py-2">
                                <span className="text-black-800 text-xs font-medium">{theme.title}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </section>
        </div>
    );
}

/** Form-level ops: title, settings, theme. */
import { type FormTheme, THEME_STYLES, ThemeColors } from '@app/constants/theme';

import { IMAGE_URL_ERROR, firstPartyImageUrl } from '../images';
import { checkedFormLanguage, formLanguageName } from '../languages';
import { OpError, clone } from '../model';
import type { FormSettingsPatch, SetFormLanguageOp, SetThemePresetOp, UpdateFormInfoOp, UpdateFormSettingsOp, UpdateThemeOp } from '../types';
import { type Handler, setKey } from './context';
import { checkMaxLength } from './fields';

export const updateFormInfo: Handler<UpdateFormInfoOp> = (ctx, op) => {
    const changed: string[] = [];
    if (op.title != null) {
        ctx.draft.title = op.title;
        if (ctx.draft.welcomePage != null) ctx.draft.welcomePage.title = op.title;
        changed.push('title');
    }
    if (op.description != null) {
        ctx.draft.description = op.description;
        changed.push('description');
    }
    if (!changed.length) throw new OpError('The update contained no changes.');
    return `Updated form ${changed.join(', ')}`;
};

const SETTINGS_LABELS: Record<keyof FormSettingsPatch, string> = {
    purpose: 'purpose',
    retentionText: 'retention',
    privacyPolicyUrl: 'privacy policy link',
    requireVerifiedIdentity: 'verified-identity requirement',
    allowEditingResponse: 'response editing',
    showSubmissionNumber: 'submission numbers'
};
const SETTINGS_TEXT_KEYS = ['purpose', 'retentionText', 'privacyPolicyUrl'] as const;
const SETTINGS_SWITCH_KEYS = ['requireVerifiedIdentity', 'allowEditingResponse', 'showSubmissionNumber'] as const;

const MAX_POLICY_URL_LENGTH = 2048;
const UNSAFE_URL = /[\s\x00-\x1f\x7f]/;

/** An absolute http(s) URL, '' for a blank one (backend `checked_policy_url`). */
export function checkedPolicyUrl(url: string, message = 'The privacy policy link must be an http(s) URL.'): string {
    const trimmed = url.trim();
    if (!trimmed) return '';
    if (trimmed.length > MAX_POLICY_URL_LENGTH || UNSAFE_URL.test(trimmed)) throw new OpError(message);
    let parsed: URL;
    try {
        parsed = new URL(trimmed);
    } catch {
        throw new OpError(message);
    }
    if ((parsed.protocol !== 'http:' && parsed.protocol !== 'https:') || !parsed.hostname) throw new OpError(message);
    return trimmed;
}

/**
 * Put a settings patch on `settings`, in place: text is trimmed and ''
 * clears it, switches are set as given (backend `apply_settings_ops`).
 */
export function applySettingsPatch(settings: Record<string, any>, patch: FormSettingsPatch): void {
    for (const key of SETTINGS_TEXT_KEYS) {
        const value = patch[key];
        if (value != null) setKey(settings, key, value.trim() || undefined);
    }
    for (const key of SETTINGS_SWITCH_KEYS) {
        const value = patch[key];
        if (value != null && settings[key] !== value) settings[key] = value;
    }
}

/**
 * Settings live on the workspace's form settings, not the form body: the
 * backend's engine checks and reports, and the save writes them. The
 * builder's document carries them in `settings`, so they are written there
 * too (unless `applySettings` is false).
 */
export const updateFormSettings: Handler<UpdateFormSettingsOp> = (ctx, op) => {
    const patch = op.patch ?? {};
    const changed = (Object.keys(SETTINGS_LABELS) as Array<keyof FormSettingsPatch>).filter((key) => patch[key] != null).map((key) => SETTINGS_LABELS[key]);
    if (!changed.length) {
        throw new OpError('Nothing to change — provide at least one of: purpose, retentionText, privacyPolicyUrl, requireVerifiedIdentity, allowEditingResponse, showSubmissionNumber.');
    }
    if (patch.privacyPolicyUrl != null) checkedPolicyUrl(patch.privacyPolicyUrl);
    if (ctx.options.applySettings !== false) {
        if (ctx.draft.settings == null) ctx.draft.settings = {} as any;
        applySettingsPatch(ctx.draft.settings as Record<string, any>, patch);
    }
    return 'Updated form settings: ' + changed.join(', ');
};

/**
 * The form's own language (`settings.language`), a key of the form itself:
 * written whatever `applySettings` says (backend `_apply_set_form_language`).
 */
export const setFormLanguage: Handler<SetFormLanguageOp> = (ctx, op) => {
    const tag = checkedFormLanguage(op.language);
    if (tag == null) {
        if (ctx.draft.settings != null) setKey(ctx.draft.settings, 'language', undefined);
        return "Cleared the form's language";
    }
    if (ctx.draft.settings == null) ctx.draft.settings = {} as any;
    setKey(ctx.draft.settings, 'language', tag);
    return `Set the form's language to ${formLanguageName(tag)} (${tag})`;
};

const THEME_KEYS = ['title', 'primary', 'secondary', 'tertiary', 'accent'] as const;

export const updateTheme: Handler<UpdateThemeOp> = (ctx, op) => {
    const theme = clone(op.theme) as FormTheme;
    for (const key of THEME_KEYS) if (typeof theme?.[key] !== 'string') throw new OpError(`theme.${key}: Field required`);
    const background = theme.background;
    if (background != null && background.imageUrl != null) {
        // Respondent pages load it directly: our storage or Unsplash only
        // (backend checked_image_url: a blank address clears the image).
        if (!String(background.imageUrl).trim()) delete background.imageUrl;
        else {
            const checked = firstPartyImageUrl(background.imageUrl, ctx.options);
            if (checked === null) throw new OpError(`Background image refused: ${IMAGE_URL_ERROR}`);
            background.imageUrl = checked;
        }
    }
    ctx.draft.theme = theme;
    return `Applied theme '${op.theme.title}'`;
};

/** Old preset names and the preset each now means (backend LEGACY_PRESET_NAMES). */
const LEGACY_PRESET_NAMES: Record<string, string> = { Blue: 'Ocean', Green: 'Forest', Red: 'Cherry', Black: 'Mono', Orange: 'Sunset', Purple: 'Lavender' };

/** The preset a name means, in any case (backend `preset_name`). */
export function presetByName(name: string | null | undefined): FormTheme | undefined {
    if (typeof name !== 'string') return undefined;
    const key = name.trim().toLowerCase();
    const legacy = Object.entries(LEGACY_PRESET_NAMES).find(([old]) => old.toLowerCase() === key);
    const wanted = legacy ? legacy[1].toLowerCase() : key;
    return ThemeColors.find((preset) => preset.title.toLowerCase() === wanted);
}

export const setThemePreset: Handler<SetThemePresetOp> = (ctx, op) => {
    checkMaxLength(op.name, 60);
    checkMaxLength(op.style, 30);
    const preset = presetByName(op.name);
    if (!preset) throw new OpError(`There is no theme preset named '${op.name}'. Pick one of: ${ThemeColors.map((t) => t.title).join(', ')}.`);
    const theme: FormTheme = { title: preset.title, primary: preset.primary, secondary: preset.secondary, tertiary: preset.tertiary, accent: preset.accent };
    if (preset.style) theme.style = preset.style;
    if (op.style != null) {
        const style = op.style.trim().toLowerCase();
        if (!(THEME_STYLES as readonly string[]).includes(style)) throw new OpError(`There is no style named '${op.style}'. Pick one of: ${THEME_STYLES.join(', ')}.`);
        theme.style = style as FormTheme['style'];
    } else if (theme.style == null && ctx.state.theme != null && ctx.state.theme.style != null) {
        theme.style = ctx.state.theme.style;
    }
    ctx.draft.theme = theme;
    return `Applied the '${theme.title}' theme${theme.style ? ` in the ${theme.style} style` : ''}`;
};

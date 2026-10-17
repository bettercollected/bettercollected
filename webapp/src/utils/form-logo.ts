/**
 * The organisation logo a form shows at the top of every respondent page
 * (DESIGN.md §9, "Organisation logo"). The file itself is uploaded through
 * the form's logo endpoint and stored in our own storage; these are the
 * rules for showing it.
 */
import { FormSlideLayout } from '@app/models/enums/form';

/** Where the logo sits: on the column's left edge or centred on it. */
export type LogoPosition = 'left' | 'center';
/** The creator's setting: `auto` (and unset) follows the welcome page. */
export type LogoPositionSetting = LogoPosition | 'auto';

export interface FormLogoSettings {
    logo?: string | null;
    logoPosition?: LogoPositionSetting | null;
    logoAlt?: string | null;
    useWorkspaceLogo?: boolean | null;
    /** For the automatic position: the welcome page's layout and the form's style. */
    welcomePage?: { layout?: FormSlideLayout | string | null } | null;
    theme?: { style?: string | null } | null;
}

export interface WorkspaceIdentity {
    title?: string | null;
    workspaceName?: string | null;
    profileImage?: string | null;
}

export interface ResolvedFormLogo {
    src: string;
    alt: string;
    position: LogoPosition;
    /** The workspace's profile image, shown because the form has none of its own. */
    fromWorkspace: boolean;
}

/** Files the upload takes (the backend checks the bytes again). */
export const LOGO_ACCEPT = 'image/png,image/jpeg,image/webp';
export const LOGO_MAX_BYTES = 1024 * 1024;
export const LOGO_ALT_MAX_LENGTH = 150;

/**
 * The logo's position. An explicit Left or Centre wins; otherwise (unset or
 * `auto`) it follows the welcome page: a centred welcome page centres the
 * logo on every page of the form, anything else keeps it on the left. A
 * Leaflet welcome page reads from one left edge, so the logo stays left.
 */
export function logoPositionFor(form: Pick<FormLogoSettings, 'logoPosition' | 'welcomePage' | 'theme'> | null | undefined): LogoPosition {
    if (form?.logoPosition === 'left' || form?.logoPosition === 'center') return form.logoPosition;
    if (form?.theme?.style === 'leaflet') return 'left';
    return form?.welcomePage?.layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND ? 'center' : 'left';
}

/**
 * What the logo strip shows, or null for no strip: the form's own logo, else
 * the workspace's profile image when the creator chose that. The alt text is
 * the creator's, else the organisation's (workspace's) name: a logo that is
 * the organisation's name in letters still names it once.
 */
export function resolveFormLogo(form: FormLogoSettings | null | undefined, workspace?: WorkspaceIdentity | null): ResolvedFormLogo | null {
    const own = form?.logo?.trim();
    const fallback = form?.useWorkspaceLogo ? workspace?.profileImage?.trim() : '';
    const src = own || fallback;
    if (!src) return null;
    const alt = form?.logoAlt?.trim() || workspace?.title?.trim() || workspace?.workspaceName?.trim() || '';
    return {
        src,
        alt,
        position: logoPositionFor(form),
        fromWorkspace: !own
    };
}

/** A plain-language reason a picked file can't be the logo, or null when it may be uploaded. */
export function logoFileProblem(file: Pick<File, 'type' | 'size'>): string | null {
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) return 'Use a PNG, JPEG or WebP image. SVG files are not accepted.';
    if (file.size > LOGO_MAX_BYTES) return 'The logo must be 1 MB or smaller.';
    return null;
}

/** The message for a refused upload (the backend answers 413, 415 or 422). */
export function logoUploadError(status?: number, detail?: unknown): string {
    if (status === 413) return 'The logo must be 1 MB or smaller.';
    if (status === 415) return 'Use a PNG, JPEG or WebP image. SVG files are not accepted.';
    if (status === 422 && typeof detail === 'string' && detail.trim()) return detail;
    return 'The logo could not be uploaded. Try again.';
}

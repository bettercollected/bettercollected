import { selectForm, selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { ResolvedFormLogo, resolveFormLogo } from '@app/utils/form-logo';

/** The logo the respondent's form shows (the published form, or the preview). */
export function useResponderFormLogo(): ResolvedFormLogo | null {
    const form = useAppSelector(selectResponderForm);
    const workspace = useAppSelector(selectWorkspace);
    return resolveFormLogo(form, workspace);
}

/**
 * The logo on the builder canvas: the draft's uploaded file with the
 * settings as they are being edited, so the canvas shows what respondents
 * will see.
 */
export function useBuilderFormLogo(): ResolvedFormLogo | null {
    const form = useAppSelector(selectForm);
    const { formState } = useFormState();
    const workspace = useAppSelector(selectWorkspace);
    return resolveFormLogo(
        {
            logo: form?.logo,
            logoPosition: formState.logoPosition ?? form?.logoPosition,
            logoAlt: formState.logoAlt ?? form?.logoAlt,
            useWorkspaceLogo: formState.useWorkspaceLogo ?? form?.useWorkspaceLogo,
            // the automatic position follows the welcome page as it is being edited
            welcomePage: formState.welcomePage ?? form?.welcomePage,
            theme: formState.theme ?? form?.theme
        },
        workspace
    );
}

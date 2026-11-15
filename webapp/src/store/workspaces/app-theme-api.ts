import type { AppTheme } from '@app/lib/app-theme';
import { workspacesApi } from '@app/store/workspaces/api';
import { setAppTheme } from '@app/store/workspaces/slice';

// The workspace's app theme (backend services/app_theme, docs/app-theme.md). The server answers 403 to a member
// without `workspace.manage`, 422 `app_theme_disabled` to a choice of `pigment` while its APP_THEME_PIGMENT_ENABLED
// is off, and 422 to anything that is not one of the two themes. The card is only offered while `appThemeEnabled` of
// the workspace permissions is true.

/** `PUT /workspaces/{id}/app-theme`: the theme the workspace is served now. On success the workspace in the store follows at once. */
export const appThemeApi = workspacesApi.injectEndpoints({
    endpoints: (builder) => ({
        setWorkspaceAppTheme: builder.mutation<{ appTheme: AppTheme }, { workspaceId: string; appTheme: AppTheme }>({
            query: ({ workspaceId, appTheme }) => ({ url: `/workspaces/${workspaceId}/app-theme`, method: 'PUT', body: { appTheme } }),
            async onQueryStarted({ workspaceId }, { dispatch, queryFulfilled }) {
                try {
                    const { data } = await queryFulfilled;
                    dispatch(setAppTheme({ workspaceId, appTheme: data.appTheme }));
                } catch {
                    // a refusal changes nothing; the card says why
                }
            }
        })
    })
});

export const { useSetWorkspaceAppThemeMutation } = appThemeApi;

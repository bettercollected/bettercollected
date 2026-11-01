import { useCallback, useEffect, useMemo, useRef } from 'react';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { selectAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { WORKSPACE_PERMISSIONS_TAG, useGetWorkspacePermissionsQuery, workspacesApi } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

/**
 * What the signed-in user may do in the current workspace, from
 * `GET /workspaces/{id}/permissions`. `can(permission)` is false until the
 * permissions have loaded (and when the request fails), so admin controls
 * never flash for members. The cache is per user and is dropped when the
 * signed-in user changes or signs out. `ready` turns true once the answer has
 * arrived, for choices that must not be made on the empty set; `answered`
 * only when it arrived successfully, for choices that must not be made on a
 * failed request either (a failure grants nothing, but it does not prove that
 * the user lacks a permission).
 */
export function useWorkspacePermissions() {
    const dispatch = useAppDispatch();
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const workspaceId: string | undefined = workspace?.id;
    const userId: string = auth?.id ?? '';

    const previousUser = useRef(userId);
    useEffect(() => {
        if (previousUser.current !== userId) {
            previousUser.current = userId;
            dispatch(workspacesApi.util.invalidateTags([WORKSPACE_PERMISSIONS_TAG]));
        }
    }, [dispatch, userId]);

    const { data, isLoading, isError, isSuccess } = useGetWorkspacePermissionsQuery(
        { workspaceId: workspaceId as string, userId },
        {
            skip: !workspaceId || !userId,
            // one fetch per workspace: every list row asks
            refetchOnMountOrArgChange: false
        }
    );
    const permissions = useMemo(() => new Set<WorkspacePermission>(!userId || isError ? [] : (data?.permissions ?? [])), [data, isError, userId]);
    const can = useCallback((permission: WorkspacePermission) => permissions.has(permission), [permissions]);
    // Settled: the answer for this workspace and user has arrived (or failed,
    // which grants nothing). False while the workspace or user is unknown.
    const ready = !!workspaceId && !!userId && (isSuccess || isError);
    // The server's answer, not a failure: only then does a missing
    // permission mean the user does not have it.
    const answered = !!workspaceId && !!userId && !!isSuccess && !isError;
    // Whether the server takes field rules (its FIELD_RULES_ENABLED), told with the permissions.
    const fieldRulesEnabled = !!userId && !isError && !!data?.fieldRulesEnabled;
    // Likewise for choice logic (its CHOICE_LOGIC_ENABLED): option logic and filters in the builder.
    const choiceLogicEnabled = !!userId && !isError && !!data?.choiceLogicEnabled;
    // The same for the newer question types (its NEW_QUESTION_TYPES_ENABLED): the builder offers them from it.
    const newQuestionTypesEnabled = !!userId && !isError && !!data?.newQuestionTypesEnabled;
    // ...and the address question (its ADDRESS_QUESTION_ENABLED), and whether its street and city lookup works (ADDRESS_LOOKUP_ENABLED too).
    const addressQuestionEnabled = !!userId && !isError && !!data?.addressQuestionEnabled;
    const addressLookupEnabled = !!userId && !isError && !!data?.addressLookupEnabled;
    // ...and the signature question (its SIGNATURE_QUESTION_ENABLED).
    const signatureQuestionEnabled = !!userId && !isError && !!data?.signatureQuestionEnabled;
    // ...and layout containers: panels, tabs and field sets (its LAYOUT_CONTAINERS_ENABLED).
    const layoutContainersEnabled = !!userId && !isError && !!data?.layoutContainersEnabled;
    // ...and whether it lets respondents save drafts (its SAVE_DRAFTS_ENABLED): the setting is read-only while it is off.
    const saveDraftsEnabled = !!userId && !isError && !!data?.saveDraftsEnabled;
    // ...and the Versions page of a form (its FORM_REVISIONS_UI_ENABLED): list, compare and restore.
    const formRevisionsUiEnabled = !!userId && !isError && !!data?.formRevisionsUiEnabled;
    return { can, permissions, isLoading, ready, answered, fieldRulesEnabled, choiceLogicEnabled, newQuestionTypesEnabled, addressQuestionEnabled, addressLookupEnabled, signatureQuestionEnabled, layoutContainersEnabled, saveDraftsEnabled, formRevisionsUiEnabled };
}

import { useTranslation } from 'react-i18next';

import { workspaceDisplayName } from '@app/utils/workspace-display-name';

/**
 * The workspace's name for the workspace's own team: its title or readable
 * handle, else the translated "Your workspace". Never the id the handle
 * defaults to.
 */
export default function useWorkspaceLabel() {
    const { t } = useTranslation();
    return (workspace?: Parameters<typeof workspaceDisplayName>[0]) => workspaceDisplayName(workspace) ?? t('WORKSPACE.FALLBACK_NAME');
}

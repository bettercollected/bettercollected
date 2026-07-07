import BottomSheetModalWrapper from '@Components/modals/modal-wrapper/bottom-sheet-modal-wrapper';
import WorkspaceSettingsContent from '@Components/workspace/workspace-settings-content';

// Kept for the deep-link flows (URL updates) that open settings from other
// dashboard pages; the primary settings surface is inside the Public
// Workspace frame, rendering the same WorkspaceSettingsContent.
export default function WorkspaceSettingsModal({ initialIndex = 0 }: { initialIndex?: number }) {
    return (
        <BottomSheetModalWrapper className="!px-0 pb-10">
            <WorkspaceSettingsContent initialIndex={initialIndex} />
        </BottomSheetModalWrapper>
    );
}

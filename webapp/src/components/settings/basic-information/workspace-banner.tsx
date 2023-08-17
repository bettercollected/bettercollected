import BannerImageComponent from '@app/components/dashboard/banner-image';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';

export default function WorkspaceBanner() {
    const workspace: WorkspaceDto = useAppSelector((state) => state.workspace);
    return (
        <div className="!my-9 md:w-[674px] w-full rounded-[8px] bg-white">
            <BannerImageComponent workspace={workspace} isFormCreator={true} />
        </div>
    );
}

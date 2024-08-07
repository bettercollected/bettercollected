import BannerImageComponent from '@Components/dashboard/banner-image';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';

export default function WorkspaceBanner() {
    const workspace: WorkspaceDto = useAppSelector((state) => state.workspace);
    return (
        <div className="!my-9 md:max-w-[320px] w-full rounded-[8px] bg-white">
            <BannerImageComponent workspace={workspace} isFormCreator={true} />
        </div>
    );
}

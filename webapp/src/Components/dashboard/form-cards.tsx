
import environments from '@app/configs/environments';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import WorkspaceFormCard from '@Components/workspace-dashboard/workspace-form-card';
import Link from 'next/link';

interface FormCardsProps {
    title: string;
    formsArray: Array<StandardFormDto>;
    workspace: WorkspaceDto;
    isFormCreator: boolean;
    showPinned?: boolean;
    showVisibility?: boolean;
}

const FormCards = ({ title, formsArray, workspace, showPinned = true, showVisibility }: FormCardsProps) => {
    const isCustomDomain = window?.location.host !== environments.FORM_DOMAIN;

    if (formsArray.length === 0) return <></>;
    return (
        <div data-testid="form-cards-container">
            {!!title && <h1 className="text-gray-700 font-semibold text-md md:text-lg mb-6">{title + ' (' + formsArray.length + ')'}</h1>}
            <div className="flex flex-col gap-4">
                {formsArray.map((form: StandardFormDto, idx: number) => {
                    const slug = form.settings?.customUrl;
                    const pathname = isCustomDomain ? `/forms/${slug}` : `/${workspace.workspaceName}/forms/${slug}`;
                    return (
                        <Link
                            key={form.formId + idx}
                            href={pathname}
                        >
                            <WorkspaceFormCard isResponderPortal showVisibility={showVisibility} showPinned={showPinned} form={form} hasCustomDomain={isCustomDomain} workspace={workspace} />
                        </Link>
                    );
                })}
            </div>
        </div>
    );
};
export default FormCards;
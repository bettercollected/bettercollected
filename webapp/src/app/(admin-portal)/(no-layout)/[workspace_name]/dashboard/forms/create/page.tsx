'use client';

import React, { use, useEffect } from 'react';

import { useRouter } from 'next-nprogress-bar';

import AIIcon from '@Components/icons/ai-icon';
import { GoogleFormIcon } from '@Components/icons/google-form';
import useDrivePicker from '@fyelci/react-google-drive-picker';
import cn from 'classnames';
import { useSetAtom } from 'jotai';
import { FileText } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useModal } from '@app/components/modal-views/context';
import ImportPdfDialog from '@app/components/pdf-import/import-pdf-dialog';
import { defaultForm } from '@app/constants/form';
import { googleFormsImport } from '@app/constants/locales/google-forms-import';
import { useGoogleFormsImportMode } from '@app/lib/hooks/use-google-forms-import-mode';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { useDialogModal } from '@app/lib/hooks/use-dialog-modal';
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from '@app/shadcn/components/ui/sheet';
import { useAppSelector } from '@app/store/hooks';
import { initialFormState } from '@app/store/jotai/form';
import { resetFromServerAtom } from '@app/store/jotai/form-document';
import { useCreateV2FormMutation } from '@app/store/redux/form-api';
import { useCreateFormFromTemplateMutation, useGetTemplatesQuery } from '@app/store/redux/template-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import FormTypeSelectionComponent from '@app/views/molecules/form-builder/form-type-selection-component';
import NavBar from '@app/views/molecules/form-builder/navbar';
import WelcomePage from '@app/views/organism/form/welcome-page';
import LayoutWrapper from '@app/views/organism/layout/layout-wrapper';

// One quiet card for every way to start a form: Sireto blue icons, a hairline
// edge that turns blue on hover. No per-card accent colours (see DESIGN.md).
const CardVariants = {
    blue: 'text-brand-500 hover:border-brand-500 hover:bg-black-100 transition-colors',
    purple: 'text-brand-500 hover:border-brand-500 hover:bg-black-100 transition-colors',
    pink: 'text-brand-500 hover:border-brand-500 hover:bg-black-100 transition-colors'
};

export default function CreateFormPage(props: { searchParams: Promise<{ modal?: string }> }) {
    const searchParams = use(props.searchParams);
    const [createV2Form] = useCreateV2FormMutation();
    const resetFromServer = useSetAtom(resetFromServerAtom);
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const [openPicker] = useDrivePicker();
    const { openModal } = useModal();
    const { openDialogModal } = useDialogModal();
    const isMobile = useIsMobile();
    const { can, isLoading: permissionsLoading } = useWorkspacePermissions();
    const canCreate = can(WorkspacePermission.FORM_CREATE);
    const { t } = useTranslation();
    // Google Forms imports only while the instance allows them
    // (GOOGLE_FORMS_IMPORT=on); unknown (the provider list failed): as before.
    const { mode: googleImportMode, isLoading: googleImportModeLoading } = useGoogleFormsImportMode();
    const showGoogleImport = !googleImportModeLoading && (googleImportMode === undefined || googleImportMode === 'on');

    // Reviewers, Viewers and Privacy officers don't create forms.
    useEffect(() => {
        if (!permissionsLoading && workspace?.id && !canCreate) {
            router.replace(`/${workspace?.workspaceName}/dashboard/forms`);
        }
    }, [permissionsLoading, canCreate, workspace?.id, workspace?.workspaceName, router]);

    const showModal = searchParams.modal;
    const [pdfImportOpen, setPdfImportOpen] = React.useState(false);

    useEffect(() => {
        if (showModal === 'true' && canCreate) {
            openModal('IMPORT_FORMS', { nonClosable: true });
        }
    }, [showModal, canCreate]);

    const { data: templates } = useGetTemplatesQuery({ v2: true }, { skip: !canCreate });

    const [createFormFrmTemplate] = useCreateFormFromTemplateMutation();

    const handleCreateForm = async (type: string) => {
        const isMultiPage = type === 'Modern Form';
        // A new form starts from an empty document with no undo history.
        resetFromServer({ ...initialFormState, fields: [] });
        // New forms default to a calm, single-column layout with no decorative
        // image (see DESIGN.md §3). Creators opt into the image / split
        // layout per page via the Layout panel.
        const updatedForm = { ...defaultForm };
        const formBody = { ...updatedForm, builderVersion: 'v2', isMultiPage };
        const formData = new FormData();
        formData.append('form_body', JSON.stringify(formBody));
        const apiRequestBody: any = { workspaceId: workspace.id, body: formData };
        const response: any = await createV2Form(apiRequestBody);
        if (response?.data) {
            router.replace(`/${workspace?.workspaceName}/dashboard/forms/${response?.data?.formId}/edit?showTitle=true`);
        }
    };

    const createFormFromTemplate = async (templateId: string) => {
        const response: any = await createFormFrmTemplate({
            workspace_id: workspace.id,
            template_id: templateId
        });
        const editFormUrl = `/${workspace.workspaceName}/dashboard/forms/${response?.data?.formId}/edit`;
        router.push(editFormUrl);
    };

    return (
        <div className="min-h-screen bg-white">
            <NavBar />
            <div className="px-auto h-body-content overflow-auto">
                <div className="mx-auto flex w-full max-w-[1330px] flex-col px-5 md:px-10">
                    <div className="h3-new mb-4 mt-6 text-black-800">New Form</div>
                    <div className="flex w-full flex-col flex-wrap gap-6 lg:flex-row">
                        {isMobile ? (
                            <Card variant={'blue'} icon={<PlusIcon />} content={'Create New Form'} onClick={() => {}} desktopOnly />
                        ) : (
                            <Sheet>
                                <SheetTrigger asChild>
                                    <Card variant={'blue'} icon={<PlusIcon />} content={'Create New Form'} onClick={() => {}} desktopOnly />
                                </SheetTrigger>
                                <SheetContent className="h-full w-full p-0" side={'top'} hideCloseIcon>
                                    <SheetTitle className="sr-only">Select form type</SheetTitle>
                                    <div className="h-full w-full bg-white">
                                        <NavBar isModal />
                                        <FormTypeSelectionComponent handleCreateForm={handleCreateForm} />
                                    </div>
                                </SheetContent>
                            </Sheet>
                        )}

                        {showGoogleImport && (
                            <Card
                                variant={'purple'}
                                icon={<GoogleFormIcon width={30} height={30} className="mb-2 w-full text-brand-500" />}
                                content={'Import Google Form'}
                                onClick={() => {
                                    openModal('IMPORT_FORMS', { nonClosable: true });
                                }}
                            />
                        )}
                        <Card variant={'blue'} icon={<FileText className="mb-2 h-[30px] w-full text-brand-500" />} content={'Import a PDF form'} onClick={() => setPdfImportOpen(true)} />
                        <Card
                            variant={'pink'}
                            icon={<AIIcon className="text-brand-500" />}
                            content={'Start with AI'}
                            // The dialog and its outline review fit a 375px screen.
                            onClick={() => openDialogModal('START_WITH_AI')}
                        />
                    </div>

                    {googleImportMode === 'readonly' && <p className="mt-4 text-sm text-black-700">{t(googleFormsImport.readonly.createPage)}</p>}

                    <ImportPdfDialog open={pdfImportOpen} onOpenChange={setPdfImportOpen} workspaceId={workspace?.id} workspaceName={workspace?.workspaceName} />
                    {!isMobile && (
                        <>
                            <div className="h3-new mb-4 mt-12 text-black-800">Templates</div>
                            <div className="flex w-full flex-row flex-wrap gap-x-6 gap-y-10">
                                {templates?.map((template) => (
                                    // Plain div: the scaled WelcomePage preview inside contains buttons,
                                    // and <button> can't nest inside <button> (hydration error).
                                    <div key={template?.id} className="outline-hidden" data-umami-event={'Create Form With Template'}>
                                        <div className="flex flex-col rounded-lg border border-transparent">
                                            <div
                                                data-umami-event={'Create Form With Template'}
                                               
                                                className="relative h-[157px] w-[281px] cursor-pointer overflow-hidden rounded-md border border-black-300"
                                                onClick={() => createFormFromTemplate(template.id)}
                                            >
                                                <div className="pointer-events-none h-[810px] w-[1440px] scale-[0.195]" style={{ transformOrigin: 'top left' }}>
                                                    <LayoutWrapper showDesktopLayout theme={template?.theme} disabled layout={template.welcomePage?.layout} imageUrl={template?.welcomePage?.imageUrl}>
                                                        <WelcomePage isPreviewMode theme={template?.theme} welcomePageData={template?.welcomePage} />
                                                    </LayoutWrapper>
                                                </div>
                                                <div className="absolute inset-0 z-10 bg-black-800 opacity-0 hover:opacity-20" />
                                            </div>
                                            <div className="p2-new mt-2 font-medium!">{template.title}</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

interface CardWrapperProps {
    icon: React.ReactNode;
    content: React.ReactNode;
    onClick: any;
    variant: 'blue' | 'purple' | 'pink';
    addSoon?: boolean;
    soonMsg?: string;
    /** Says so below the desktop breakpoint (the blank-form builder). */
    desktopOnly?: boolean;
}

const Card = ({ icon, content, onClick, variant, addSoon, soonMsg, desktopOnly }: CardWrapperProps) => {

    return (
        <div
            data-umami-event={content}
           
            className={cn('relative flex h-[170px] w-full cursor-pointer flex-col items-center justify-center overflow-hidden rounded border border-black-400 bg-white lg:h-[117px] lg:w-[220px]', CardVariants[variant])}
            onClick={onClick}
        >
            {icon}
            <span className="p3-new mb-1 mt-2 text-black-800">{content}</span>
            {desktopOnly && <OnlyAvailableInDesktopVersion />}
            {addSoon && <SoonComponent msg={soonMsg} />}
            {content === 'Start with AI' && <div className="absolute right-2 top-2 flex rounded bg-brand-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-brand-600">beta</div>}
        </div>
    );
};

const SoonComponent = ({ msg }: { msg?: string }) => {
    return (
        <div className="absolute right-2 top-2 rounded bg-black-200 px-1.5 py-0.5 text-[11px] font-medium text-black-700">{msg || 'Soon'}</div>
    );
};

const OnlyAvailableInDesktopVersion = () => {
    return (
        <div className="absolute bottom-2 text-xs text-black-600 lg:hidden">Only available on desktop</div>
    );
};

const PlusIcon = () => {
    return (
        <svg width="41" height="40" viewBox="0 0 41 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20 11L20 29" stroke="#123FC9" strokeWidth="2" strokeLinecap="round" />
            <path d="M11 20H29" stroke="#123FC9" strokeWidth="2" strokeLinecap="round" />
        </svg>
    );
};

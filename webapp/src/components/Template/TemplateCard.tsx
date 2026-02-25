import { useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/legacy/image';




import { useBottomSheetModal } from '@app/components/Modals/Contexts/BottomSheetModalContext';
import { Loader2, MoreVertical, Pencil, Settings } from 'lucide-react';

import { IFormTemplateDto } from '@app/models/dtos/template';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import WelcomePage from '@app/views/organism/Form/WelcomePage';
import LayoutWrapper from '@app/views/organism/Layout/LayoutWrapper';

interface ITemplateCardProps {
    template: IFormTemplateDto;
    isPredefinedTemplate: boolean;
}

const TemplateCard = ({ template, isPredefinedTemplate }: ITemplateCardProps) => {
    // const router = useRouter();
    // const workspace = useAppSelector(selectWorkspace);

    const { t } = useTranslation();

    const { openBottomSheetModal } = useBottomSheetModal();
    const [open, setOpen] = useState(false);

    return (
        <div className={`flex min-w-[150px] flex-col gap-2 md:min-w-[186px] ${template?.builderVersion !== 'v2' && 'w-[150px]'}`}>
            <div
                className={`border-black-200  hover:shadow-hover relative  cursor-pointer overflow-hidden rounded border md:h-[192px] ${!template.previewImage && template?.builderVersion === 'v2' ? '!h-[157px] w-[281px]' : 'flex h-[170px] items-center justify-center bg-gradient-to-b from-blue-400 to-blue-800 '
                    }`}
            // onClick={handleClickCard}
            >
                {template?.builderVersion !== 'v2' && (
                    <>
                        {template?.previewImage ? (
                            <Image alt={template.title} src={template.previewImage} layout={'fill'} />
                        ) : (
                            <Loader2 className="animate-spin text-[#F2F7FF]" size={24} />
                        )}
                    </>
                )}
                {template?.builderVersion === 'v2' && (
                    <div className="relative h-[157px] w-[281px] overflow-hidden rounded-md">
                        <div className="pointer-events-none h-[810px] w-[1440px] scale-[0.195]" style={{ transformOrigin: 'top left' }}>
                            <LayoutWrapper theme={template?.theme} disabled layout={template.welcomePage?.layout} imageUrl={template?.welcomePage?.imageUrl}>
                                <WelcomePage isPreviewMode theme={template?.theme} welcomePageData={template?.welcomePage} />
                            </LayoutWrapper>
                        </div>
                    </div>
                    // <div className="flex cursor-pointer flex-col rounded-lg border border-transparent p-1 hover:border-pink-500" key={template?.id}>

                    //     <div className="p2-new mt-2 !font-medium">{template.title}</div>
                    // </div>
                )}
            </div>
            <div className="flex w-full items-start justify-between">
                <div className="flex flex-col gap-[5px]">
                    <span className={'h5-new text-black-800 max-w-[110px] truncate font-semibold md:max-w-[150px]'}>{template.title || t('UNTITLED')}</span>
                    {!isPredefinedTemplate && (
                        <h1 className={'text-black-600 text-xs font-normal'}>
                            {t('TEMPLATE.CREATED')}: <span className={'text-black-800'}>{template?.importedFrom ? template.importedFrom : t('TEMPLATE.DEFAULT')}</span>
                        </h1>
                    )}
                </div>
                {!isPredefinedTemplate && (
                    <Popover open={open} onOpenChange={setOpen}>
                        <PopoverTrigger asChild>
                            <div className="cursor-pointer">
                                <MoreVertical width={24} height={24} className="text-black-800" />
                            </div>
                        </PopoverTrigger>
                        <PopoverContent
                            align="end"
                            className="w-[180px] p-0"
                            onClick={() => setOpen(false)}
                            onInteractOutside={() => setOpen(false)}
                        >
                            <ul className="list-none m-0 p-0 bg-white rounded shadow-[0px_0px_12px_0px_rgba(7,100,235,0.45)]">
                                {template?.builderVersion !== 'v2' && (
                                    <li
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            // handleClickEditCard();
                                            setOpen(false);
                                        }}
                                        className="flex items-center gap-2 px-4 py-2 hover:bg-black-100 cursor-pointer body4"
                                    >
                                        <div className="text-black-600 flex items-center justify-center">
                                            <Pencil width={20} height={20} strokeWidth={2} />
                                        </div>
                                        <span>{t('BUTTON.EDIT')}</span>
                                    </li>
                                )}
                                <li
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        openBottomSheetModal('TEMPLATE_SETTINGS_FULL_MODAL_VIEW', { template, showTitle: true });
                                        setOpen(false);
                                    }}
                                    className="flex items-center gap-2 px-4 py-2 hover:bg-black-100 cursor-pointer body4"
                                >
                                    <div className="text-black-600 flex items-center justify-center">
                                        <Settings width={20} height={20} />
                                    </div>
                                    <span>{t('SETTINGS')}</span>
                                </li>
                            </ul>
                        </PopoverContent>
                    </Popover>
                )}
            </div>
        </div>
    );
};
export default TemplateCard;

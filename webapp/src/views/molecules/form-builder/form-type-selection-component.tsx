import { useTranslation } from 'react-i18next';
import { MultiPageFormIcon } from '@Components/icons/multipage-form-icon';
import { SinglePageFormIcon } from '@Components/icons/single-page-form-icon';

interface IFormTypes {
    type: string;
    icon: React.ReactNode;
    title: string;
    description: string;
}
const FormTypes: IFormTypes[] = [
    {
        type: 'Modern Form',
        icon: <MultiPageFormIcon />,
        title: 'FORM_TYPE.MODERN',
        description: 'FORM_TYPE.MODERN_HINT'
    },
    {
        type: 'Classic Form',
        icon: <SinglePageFormIcon />,
        title: 'FORM_TYPE.CLASSIC',
        description: 'FORM_TYPE.CLASSIC_HINT'
    }
];

const FormTypeSelectionComponent = ({ handleCreateForm }: { handleCreateForm: (type: any) => void }) => {
    const { t } = useTranslation('builder');

    return (
        <div className="flex flex-col items-center gap-20 py-12">
            <div className="flex flex-col items-center gap-1">
                <span className="text-black-800 text-2xl font-semibold">{t('FORM_TYPE.TITLE')}</span>
                <span className="text-black-600 text-sm font-normal">{t('FORM_TYPE.HINT')}</span>
            </div>
            <div className="flex flex-row gap-12">
                {FormTypes.map((item: IFormTypes) => {
                    return (
                        <button key={item.type} autoFocus={false} className="border-none outline-hidden active:border-none" data-umami-event={item.type}>
                            <FormTypeCard item={item} handleClick={handleCreateForm} />
                        </button>
                    );
                })}
            </div>
        </div>
    );
};

export default FormTypeSelectionComponent;

const FormTypeCard = ({ item, handleClick }: { item: IFormTypes; handleClick: (type: string) => void }) => {
    const { t } = useTranslation('builder');
    return (
        <div onClick={() => handleClick(item.type)} className="border-black-400 hover:border-brand-500 flex w-[375px] cursor-pointer flex-col overflow-hidden rounded border transition-colors">
            <div className="bg-brand-100 p-4">
                <div className="text-brand-600 w-fit rounded bg-white px-2 py-1 text-xs font-medium">
                    {item.type}
                </div>
                <div className="flex justify-center">{item.icon}</div>
            </div>
            <div className="flex flex-col gap-1 bg-white px-8 py-4">
                <span className="text-black-800 font-medium">{t(item.title)}</span>
                <span className="text-black-600 text-sm font-normal">{t(item.description)}</span>
            </div>
        </div>
    );
};

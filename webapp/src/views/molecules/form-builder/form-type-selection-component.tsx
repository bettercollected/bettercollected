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
        title: 'Multi-Page Form',
        description: 'Show single form field per page'
    },
    {
        type: 'Classic Form',
        icon: <SinglePageFormIcon />,
        title: 'Single Page Form',
        description: 'Show all form fields in a single page'
    }
];

const FormTypeSelectionComponent = ({ handleCreateForm }: { handleCreateForm: (type: any) => void }) => {

    return (
        <div className="flex flex-col items-center gap-20 py-12">
            <div className="flex flex-col items-center gap-1">
                <span className="text-black-800 text-2xl font-semibold">Select Form Type</span>
                <span className="text-black-600 text-sm font-normal">Select form type according to your need.</span>
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
    return (
        <div onClick={() => handleClick(item.type)} className="border-black-400 hover:border-brand-500 flex w-[375px] cursor-pointer flex-col overflow-hidden rounded border transition-colors">
            <div className="bg-brand-100 p-4">
                <div className="text-brand-600 w-fit rounded bg-white px-2 py-1 text-xs font-medium">
                    {item.type}
                </div>
                <div className="flex justify-center">{item.icon}</div>
            </div>
            <div className="flex flex-col gap-1 bg-white px-8 py-4">
                <span className="text-black-800 font-medium">{item.title}</span>
                <span className="text-black-600 text-sm font-normal">{item.description}</span>
            </div>
        </div>
    );
};

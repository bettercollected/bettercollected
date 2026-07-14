
import { useTranslation } from 'react-i18next';


import AnchorLink from '@app/components/ui/links/anchor-link';


interface ISettingCard {
    title: string;
    description: string;
    link: string;
}

export default function SettingCard({ title, description, link }: ISettingCard) {
    const { t } = useTranslation();

    return (
        <div className="p-6 bg-white md:w-[740px]">
            <p className="sh3">{title}</p>
            <p className="mt-4 mb-6 body4 !text-black-700">{description}</p>
            <div className="flex gap-[22px] items-center">
                <p className="body4 !text-brand-500 truncate">
                    <AnchorLink href={link} target="_blank">
                        {link}
                    </AnchorLink>
                </p>
            </div>
        </div>
    );
}
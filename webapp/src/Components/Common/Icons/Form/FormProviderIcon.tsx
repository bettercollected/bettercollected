import SmallLogo from '@Components/Common/Icons/Common/SmallLogo';
import {GoogleFormIcon} from "@Components/icons/google-form-icon";
import {TypeformIcon} from "@Components/icons/brands/typeform";

interface IFormProviderIconProps {
    provider?: string;
    size?: number;
    variant?: FormProviderVariant;
}

FormProviderIcon.defaultProps = {
    provider: 'self',
    size: 24,
    variant: 'full'
};
type FormProviderVariant = 'logo' | 'full';
export default function FormProviderIcon({ provider, size, variant }: IFormProviderIconProps) {
    const getProvider = () => {
        if (provider === 'google')
            return {
                icon: GoogleFormIcon,
                text: 'Google Forms'
            };
        if (provider === 'typeform')
            return {
                icon: TypeformIcon,
                text: 'Typeform'
            };
        return {
            icon: SmallLogo,
            text: 'bettercollected'
        };
    };

    const providerObj = getProvider();

    return (
        <div className="flex gap-2 text-sm items-center text-black-600">
            <providerObj.icon height={size} width={size} />
            {variant === 'full' && <span>{providerObj.text}</span>}
        </div>
    );
}
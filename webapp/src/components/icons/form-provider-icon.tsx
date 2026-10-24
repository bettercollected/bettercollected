import { FileText } from 'lucide-react';

import { GoogleFormIcon } from "@app/components/icons/google-form-icon";
import SmallLogo from "./small-logo";

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
        // Typeform is no longer integrated; forms imported from it keep their
        // provider, so they still say where they came from (no brand logo).
        if (provider === 'typeform')
            return {
                icon: FileText,
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
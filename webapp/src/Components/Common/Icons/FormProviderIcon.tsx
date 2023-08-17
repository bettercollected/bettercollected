import SmallLogo from '@Components/Common/Icons/SmallLogo';

import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';

interface IFormProviderIconProps {
    provider?: string;
    size?: number;
}

FormProviderIcon.defaultProps = {
    provider: 'self',
    size: 34
};
export default function FormProviderIcon({ provider, size }: IFormProviderIconProps) {
    if (provider === 'google') return <GoogleFormIcon width={size} height={size} className="-ml-1" />;
    if (provider === 'typeform') return <TypeformIcon width={size} height={size} />;
    return <SmallLogo />;
}

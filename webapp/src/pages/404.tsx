import Link from 'next/link';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import HeaderImageWrapper from '@Components/Common/Wrapper/HeaderImageWrapper';

export default function FourOhFour() {
    return (
        <HeaderImageWrapper className="my-16 gap-4">
            <span className="h2-new">404 </span>
            <div className="flex flex-col gap-2 items-center">
                <span className="h4-new text-black-800">Page Not Found</span>
                <span className="p2-new text-black-700 text-center">We’re sorry, we couldn’t find the page.</span>
            </div>
            <Link href="/">
                <AppButton variant={ButtonVariant.Tertiary}>Go back home</AppButton>
            </Link>
        </HeaderImageWrapper>
    );
}
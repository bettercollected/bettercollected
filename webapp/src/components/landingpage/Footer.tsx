/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-20
 * Time: 16:26
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import { useRouter } from 'next/router';

import TwitterIcon from '@mui/icons-material/Twitter';

import ActiveLink from '@app/components/ui/links/active-link';
import Logo from '@app/components/ui/logo';

export default function Footer() {
    const router = useRouter();

    function SectionLink(props: any) {
        const { title, path } = props;
        return (
            <p className={'cursor-pointer mb-2 hover:text-gray-600'} onClick={() => router.push(`${path}`)}>
                {title}
            </p>
        );
    }

    function FontBold(props: any) {
        return <div className={'font-semibold mb-2'}>{props.children}</div>;
    }

    return (
        <div className="relative bg-gradient-to-r from-white via-sky-50 to-red-50 mb-0 px-4 pt-24 pb-4 sm:px-6 sm:pt-24 sm:pb-20 lg:px-8 xl:px-10 3xl:px-12">
            <Logo />
            <p>Collect forms responses responsibly.</p>
            <div className="flex flex-col md:flex-row md:justify-between mt-6">
                <div>
                    <p className="text-lg font-bold">Company</p>
                    <SectionLink title="Home" path="#banner" />
                    <SectionLink title="Features" path="#features" />
                    <ActiveLink href="/contact" className="hover:text-gray-600">
                        Contact us
                    </ActiveLink>
                </div>
                <div className="mt-6 md:mt-0">
                    <p className="text-lg font-bold">Follow us on</p>
                    <ActiveLink href="https://twitter.com/BetterCollected">
                        <TwitterIcon className={'bg-gray-300 hover:bg-gray-200 cursor-pointer rounded-md p-1 h-7 w-7'} /> Twitter
                    </ActiveLink>
                </div>
                <div className="flex flex-col">
                    <ActiveLink className="mt-6 md:mt-0 text-lg font-semibold hover:text-gray-600" href="https://bettercollected.com/legal/terms-and-conditions-2022.pdf">
                        Terms and Conditions
                    </ActiveLink>
                    <ActiveLink className="mt-6 md:mt-0 text-lg font-semibold hover:text-gray-600" href="https://bettercollected.com/legal/privacy-policy-2022.pdf">
                        Privacy Policy
                    </ActiveLink>
                </div>
            </div>
        </div>
    );
}

import AnchorLink from '../ui/links/anchor-link';
import WhatsNewIcon from './Icons/WhatsNewIcon';
import ReportProblemIcon from './Icons/ReportProblemIcon';
import RequestFeatureIcon from './Icons/RequestFeatureIcon';
import ContactSupportIcon from './Icons/ContactSupportIcon';

const HelpMenuItem = () => {
    return (
        <>
            <MenuItemWrapper href="https://bettercollected.com/whats-new/">
                <WhatsNewIcon />
                What's New
            </MenuItemWrapper>
            <MenuItemWrapper href="https://forms.bettercollected.com/support/forms/report-problem">
                <ReportProblemIcon />
                Report Problem
            </MenuItemWrapper>
            <MenuItemWrapper href="https://forms.bettercollected.com/support/forms/feature-request">
                <RequestFeatureIcon />
                Request Feature
            </MenuItemWrapper>{' '}
            <MenuItemWrapper href="https://forms.bettercollected.com/support/forms/contact">
                <ContactSupportIcon />
                Contact Support
            </MenuItemWrapper>
        </>
    );
};

const MenuItemWrapper = ({ children, href }: { children: any; href: string }) => {
    return (
        <AnchorLink href={href} target="_blank" key={href}>
            <div className="hover:bg-black-200 hover:text-black-800 flex w-full items-center justify-start gap-2 rounded-lg p-2">{children}</div>
        </AnchorLink>
    );
};

export default HelpMenuItem;

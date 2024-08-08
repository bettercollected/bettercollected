import type { LinkProps } from 'next/link';
import { usePathname } from 'next/navigation';

import cn from 'classnames';

import AnchorLink from '@app/Components/ui/links/anchor-link';

interface ActiveLinkProps extends LinkProps {
    activeClassName?: string;
}

const ActiveLink: React.FC<ActiveLinkProps & Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, 'href'>> = ({ href, className, activeClassName = 'active', ...props }) => {
    const pathname = usePathname();
    return (
        <AnchorLink
            href={href}
            className={cn(className, {
                [activeClassName]: pathname === href
            })}
            {...props}
        />
    );
};

export default ActiveLink;

import { GetServerSidePropsContext } from 'next';
import dynamic from 'next/dynamic';

import environments from '@app/configs/environments';
import Layout from '@app/layouts/_layout';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { checkHasClientDomain, checkHasCustomDomain, getRequestHost } from '@app/utils/serverSidePropsUtils';

const WorkspaceHomeContainer = dynamic(() => import('@app/containers/dashboard/WorkspaceHomeContainer'), { ssr: false });

interface IHome extends IServerSideProps {}

const Home = ({ workspace }: IHome) => {
    const isCustomDomain = true;
    if (workspace)
        return (
            <Layout isCustomDomain={isCustomDomain} isClientDomain showNavbar={!isCustomDomain} hideMenu={!isCustomDomain} className="!p-0 bg-white flex flex-col min-h-screen">
                <WorkspaceHomeContainer showProTag={false} isCustomDomain={true} />
            </Layout>
        );
    return <></>;
};

export default Home;

export async function getServerSideProps(_context: GetServerSidePropsContext) {
    const hasCustomDomain = checkHasCustomDomain(_context);
    const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
    if (hasCustomDomain) {
        if (!globalProps?.workspace?.id) {
            return {
                notFound: true
            };
        }
        return {
            props: { ...globalProps }
        };
    }
    const scheme = _context.req.headers?.referer?.includes('https://') ? 'https://' : 'http://';
    const locale = globalProps['_nextI18Next']['initialLocale'] === 'en' ? '' : `${globalProps['_nextI18Next']['initialLocale']}/`;

    const hasClientDomain = checkHasClientDomain(getRequestHost(_context));
    if (hasClientDomain) {
        return {
            redirect: {
                permanent: false,
                destination: `${scheme}${environments.ADMIN_DOMAIN}`
            }
        };
    }

    return {
        redirect: {
            permanent: false,
            destination: `/${locale}login`
        }
    };
}

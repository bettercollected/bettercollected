import { GetServerSidePropsContext } from 'next';
import dynamic from 'next/dynamic';

import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { checkHasClientDomain, checkHasCustomDomain, getRequestHost } from '@app/utils/serverSidePropsUtils';

const WorkspaceHomeContainer = dynamic(() => import('@app/containers/dashboard/WorkspaceHomeContainer'), { ssr: false });

interface IHome extends IServerSideProps {}

const Home = ({ workspace }: IHome) => {
    if (workspace) return <WorkspaceHomeContainer showProTag={false} isCustomDomain={true} />;
    return <></>;
};

export default Home;

export async function getServerSideProps(_context: GetServerSidePropsContext) {
    const hasCustomDomain = checkHasCustomDomain(_context);

    if (hasCustomDomain) {
        const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
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
            destination: `/login`
        }
    };
}

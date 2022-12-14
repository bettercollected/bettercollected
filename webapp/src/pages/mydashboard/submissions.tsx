import Layout from '@app/components/sidebar/layout';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';

// import useUser from '@app/lib/hooks/use-authuser';

export default function mySubmissions() {
    // const { isLoading } = useUser();

    // if (isLoading) return <FullScreenLoader />;

    return (
        <Layout>
            Hello My submissions.
            <p>My submissions</p>
        </Layout>
    );
}

import Layout from '@app/components/sidebar/layout';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import useUser from '@app/lib/hooks/use-authuser';

export default function MySettings() {
    const { user, isLoading } = useUser();

    if (isLoading) return <FullScreenLoader />;

    const Header = () => {
        return (
            <div className=" pb-4 border-b-gray-200 border-b-[1px]">
                <h1 className="font-semibold text-2xl">Settings</h1>
                <p className="text-gray-600"> Manage your form settings and preferences.</p>
            </div>
        );
    };

    return (
        <Layout>
            <Header />
        </Layout>
    );
}

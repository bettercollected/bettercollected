import UpgradeToProContainer from '@app/containers/upgrade-to-pro';

export default function PricingPlanPage() {

    return (
        <div className="relative min-h-screen flex items-center overflow-auto !bg-white">
            <UpgradeToProContainer isModal={false} />
        </div>
    );
}

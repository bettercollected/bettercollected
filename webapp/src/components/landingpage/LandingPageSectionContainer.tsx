/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-19
 * Time: 13:54
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function LandingPageSectionContainer(props: any) {
    const { sectionId } = props;
    return (
        <div id={sectionId} className="h-full w-full">
            {props.children}
        </div>
    );
}

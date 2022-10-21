/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-19
 * Time: 13:54
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function LandingPageSectionContainer(props:any) {
    const {sectionId} = props;
    return (
        <div id={sectionId} className={"landing-section-container p-8 lg:p-12 h-full lg:w-[1350px] lg:m-auto flex flex-col justify-center"}>
            {props.children}
        </div>
    );
}
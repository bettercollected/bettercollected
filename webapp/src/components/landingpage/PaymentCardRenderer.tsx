/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-19
 * Time: 07:51
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import ButtonRenderer from "@app/components/ui/ButtonRenderer";

export default function PaymentCardRenderer(props:any) {
    const {title, description,amount,plan} = props;

    function CardHeader() {
        return (
            <>
                <div className="flex justify-between item-baseline ">
                    {/* place for icons */}
                    <span className={`text-3xl ${props.recommended? "text-[#007AFF]":""} font-semibold`}>{title}</span>
                    {props.recommended && <span className={"p-2 border-1 rounded-full text-sm bg-[#007AFF] font-normal"}>Popular</span>}
                </div>
                <p className={`font-light ${props.recommended? "text-white":"text-gray-500"} sm:text-md`}>{description}</p>
            </>
        );
    }

    function Pricing() {
        return (
            <div className="flex justify-center items-baseline my-8">
                <span className="mr-2 text-6xl font-bold">{amount}</span>
                <span className={`${props.recommended?"text-white":"text-gray-500"}`}>/{plan}</span>
            </div>
        );
    }

    function GetStartedButton() {
        return (
            <ButtonRenderer>
                {!!props.buttonTitle? props.buttonTitle: "Get Started"}
            </ButtonRenderer>
        );
    }

    function FeatureListRenderer(props:any){
        return(
            <li className={"flex items-center space-x-3"}>
                {!props.nocheckmark && <svg className="flex-shrink-0 w-5 h-5 text-green-500 dark:text-green-400"
                     fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                    <path fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"></path>
                </svg>}
                {props.children}
            </li>
        )
    }

    function PlanFeatures() {
        return (
            <ul role="list" className="mt-3 mb-8 space-y-4 text-left">
                <FeatureListRenderer nocheckmark={true}>
                    <h3 className=' text-lg font-bold'>Features</h3>
                    <p></p>
                </FeatureListRenderer>
                {props.features.map((feature:string,index:number) => (
                    <FeatureListRenderer key={index}>
                        <span>{feature}</span>
                    </FeatureListRenderer>
                ))}
            </ul>
        );
    }

    return (
        <div className={`flex flex-col w-full p-6 mx-auto max-w-lg text-start ${props.recommended? "bg-[#333333] text-white":"bg-white text-dark"} rounded-3xl shadow-lg`}>
            <CardHeader/>
            <Pricing/>
            <GetStartedButton/>
            <PlanFeatures/>
        </div>
    )
}
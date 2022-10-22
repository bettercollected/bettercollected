/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-18
 * Time: 16:01
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function ButtonRenderer(props: any) {
    const onClick = props?.onClick;
    return (
        <button
            disabled={!!props.disabled}
            className={
                `p-2 md:p-4 md:pt-2 md:pb-2 text-white rounded-md ${props.disabled? "bg-gray-400" :"bg-[#007aff] hover:bg-[#4da2ff]"} text-ellipsis`
            }
            onClick={!!onClick?onClick:()=>{}}
        >
            <span className={"z-2"}>{props.children}</span>
        </button>
    );
}
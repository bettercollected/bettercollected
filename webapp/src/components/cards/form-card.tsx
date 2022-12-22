export default function FormsCard(props: any) {
    return (
        <div className="flex flex-row items-center justify-between h-full gap-8 p-5 border-[1px] border-neutral-300 hover:border-blue-500 drop-shadow-sm hover:drop-shadow-lg transition cursor-pointer bg-white rounded-[20px]" {...props}>
            {props.children}
        </div>
    );
}

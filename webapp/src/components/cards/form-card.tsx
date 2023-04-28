export default function FormsCard(props: any) {
    return (
        <div data-testid="form-card" className="flex flex-col items-start justify-between h-full bg-brand-100 border-[1px] border-black-400 hover:border-brand-500 transition cursor-pointer rounded-[4px]" {...props}>
            {props.children}
        </div>
    );
}

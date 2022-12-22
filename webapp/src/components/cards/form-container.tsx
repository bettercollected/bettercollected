export default function FormsContainer(props: any) {
    return <div className="grid grid-cols-1 md:grid-cols-2 3xl:grid-cols-3 4xl:grid-cols-4 gap-8">{props.children}</div>;
}

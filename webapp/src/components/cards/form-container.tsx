export default function FormsContainer(props: any) {
    return (
        <div data-testid="forms-container" className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {props.children}
        </div>
    );
}

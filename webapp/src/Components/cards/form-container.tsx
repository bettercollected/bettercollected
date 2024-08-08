export default function FormsContainer(props: any) {
    return (
        <div data-testid="forms-container" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-6">
            {props.children}
        </div>
    );
}

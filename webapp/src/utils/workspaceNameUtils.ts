const predefined_names = ['forms', 'submissions', 'templates'];

export const checkIfPredefinedWorkspaceName = (name: string | null) => {
    return name && predefined_names.includes(name);
};

export const checkErrorForWorkspaceName = (name: string | null) => {
    if (name) {
        return checkIfPredefinedWorkspaceName(name) || !name.match(/^[a-zA-Z0-9_]+$/) || name.includes(' ');
    }
    return true;
};

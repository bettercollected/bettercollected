import { builder } from './builderSlice';

export const {
    addAction,
    addCondition,
    addDuplicateField,
    deleteAction,
    deleteCondition,
    setActiveChoice,
    setActiveField,
    setAddNewChoice,
    setBuilderMenuState,
    resetBuilderMenuState,
    setBuilderState,
    setCommandMenuPosition,
    setDeleteChoice,
    setDeleteField,
    setEditForm,
    setFields,
    setIdentifierField,
    setMoveField,
    resetForm,
    setAddNewField,
    setLogicalOperator,
    setTyping,
    setUpdateCommandField,
    setUpdateField,
    updateAction,
    updateConditional,
    updateConditionalOperator,
    setUpdateVisibility
} = builder.actions;

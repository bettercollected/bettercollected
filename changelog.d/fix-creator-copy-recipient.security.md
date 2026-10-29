- The "send me a copy" action can only mail a member of the form's workspace or the form's creator.
  Any other receiving address is refused when the action is added (422, `copy_recipient_not_allowed`),
  and again right before each mail is sent, so a member removed later stops receiving copies. Before,
  any address could be set and the instance's mail server sent response data to it. Addresses are
  compared after trimming whitespace and ignoring case; plus tags and dots are not ignored.

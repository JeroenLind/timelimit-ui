# requirements

Keep track of a requirements.md document. Structure this according different types of requirements.
Everytime a feature is implement add the requirements of that feature to the document

On every bug fix also extract the requirement and add it to the document

Warn the user in case of conflicting requirements

When implementing a feature make sure all existing requirements are still fulfilled

Update the design documentation on all major updates on the code base. The documentation must always be up to date

Location and format: the requirements live in `timelimit-ui/docs/requirements/requirements.md`. Every requirement has a unique ID (FR/UI/TR/NFR/SEC), a MoSCoW priority and a status. Never duplicate a requirement; change it in place. Bugs are not listed separately: a bug fix becomes (or sharpens) a requirement plus a regression test.

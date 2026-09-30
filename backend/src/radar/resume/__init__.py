"""Resume upload: from a file to a suggested reader profile.

    file -> format check -> text (docling service or the built-in parser)
         -> contact details removed -> facts and interests (model or taxonomy)

Only the extracted facts are kept. The file is deleted as soon as it has been
parsed, and the text is never stored or logged.
"""

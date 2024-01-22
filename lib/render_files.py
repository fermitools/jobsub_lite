""" Code factored out of jobsub_submit """
# pylint: disable=wrong-import-position,wrong-import-order,import-error
import glob
import os
import os.path
from typing import Union, List, Dict, Any
from tracing import as_span

import jinja2 as jinja  # type: ignore


PREFIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_basefiles(dlist: List[str]) -> List[str]:
    """get basename of files in directory"""
    res = []
    for d in dlist:
        flist = glob.glob(f"{d}/*")
        for f in flist:
            res.append(os.path.basename(f))
    return res


@as_span(name="render_files", arg_attrs=["*"])
def render_files(
    srcdir: str,
    values: Dict[str, Any],
    dest: str,
    dlist: Union[None, List[str]] = None,
    xfer: bool = True,
) -> None:
    """use jinja to render the templates from srcdir into the dest directory
    using values dict for substitutions
    """
    if values.get("verbose", 0) > 0:
        print(f"trying to render files from {srcdir}\n")

    if dlist is None:
        dlist = [srcdir]

    if xfer:
        values["transfer_files"] = get_basefiles(dlist) + values.get(
            "transfer_files", []
        )

    jinja_env = jinja.Environment(
        loader=jinja.FileSystemLoader(srcdir), undefined=jinja.StrictUndefined
    )
    jinja_env.filters["basename"] = os.path.basename
    flist = glob.glob(f"{srcdir}/*")

    # add destination dir to values for template
    values["cwd"] = dest

    for f in flist:
        if values["verbose"] > 0:
            print(f"rendering: {f}")
        bf = os.path.basename(f)
        rendered_file = os.path.join(dest, bf)
        try:
            with open(rendered_file, "w", encoding="UTF-8") as of:
                of.write(jinja_env.get_template(bf).render(**values))
        except jinja.exceptions.UndefinedError as e:
            err = f"""Cannot render template file {f} due to undefined template variables.
{e}
Please open a ticket to the Service Desk and include this error message
in its entirety.
"""
            print(err)
            raise
        if rendered_file.endswith(".sh"):
            os.chmod(rendered_file, 0o755)
        else:
            if values.get("verbose", 0) > 0:
                print(f"Created file {rendered_file}")

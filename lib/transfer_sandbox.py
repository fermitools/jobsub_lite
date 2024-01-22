# pylint: disable=wrong-import-position,wrong-import-order,import-error
import os
import os.path

from fake_ifdh import mkdir_p, cp
from tracing import as_span

PREFIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@as_span("transfer_sandbox")
def transfer_sandbox(src_dir: str, dest_url: str) -> None:
    """Transfer files from src_dir to sandbox with fake_ifdh (gfal-copy).
    Nothing failing here is considered fatal, since it doesn't affect the job
    itself, just log availability.

    """
    print("Transferring files to web sandbox...")
    try:
        mkdir_p(dest_url)
    except Exception as e:  # pylint: disable=broad-except
        print(
            f"warning: error creating sandbox, web logs will not be available for this submission: {e}"
        )
        return
    for f in os.listdir(src_dir):
        try:
            cp(os.path.join(src_dir, f), os.path.join(dest_url, f))
        except Exception as e:  # pylint: disable=broad-except
            print(
                f"warning: error copying {f} to sandbox, will not be available through web logs: {e}"
            )

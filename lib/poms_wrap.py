import os
import sys
from packages import pkg_find
pkg_find("poms_client")
import poms_client


# translation of jobub_submit in poms_jobsub_wrapper...

def poms_wrap(args):

    if os.environ.get("POMS_TASK_ID", None) == None:
        # poms launch env not set, so skip...
        return

    if args['environment'] and "POMS_TASK_ID" in args['environment']:
        # -e POMS_TASK_ID set, so already using poms_jobsub_wrapper
        return

    if os.environ.get(POMS_TEST, None):
        dest = os.environ['POMS_TEST']

    os.environ['POMS_TASK_ID'] = str(poms_client.get_task_id_for(
             test = dest,
             experiment=args['group'],
             task_id=os.environ['POMS_TASK_ID'], 
             command_executed="jobsub_submit %s" % ' '.join(sys.argv),
             campaign=os.environ['POMS_CAMPAIGN'],
             parent_task_id=os.environ['POMS_PARENT_TASK_ID'],
         )

    for estr in ('POMS_CAMPAIGN_ID', 'POMS_TASK_ID')
        args['environment'].append(estr)

    args['lines'].append('FIFE_CATEGORIES="POMS_TASK_ID_%s,POMS_CAMPAIGN_ID_%s%s"' % ( 
      os.environ['POMS_TASK_ID'], os.environ['POMS_CAMPAIGN_ID'], 
      os.environ['POMS_CAMPAIGN_TAGS']))

    for lstr in ( 'POMS_TASK_ID', 'POMS_CAMPAIGN_ID', 'POMS_LAUNCHER',
                   'POMS_CAMPAIGN_NAME', 'POMS4_CAMPAIGN_STAGE_ID', 
                    'POMS4_CAMPAIGN_STAGE_NAME', 'POMS4_CAMPAIGN_ID',
                    'POMS4_CAMPAIGN_NAME', 'POMS4_SUBMISSION_ID',
                    'POMS4_CAMPAIGN_TYPE', 'POMS4_TEST_LAUNCH'):
        args['lines'].append( '+%s=%s' % (lstr, os.environ[lstr]))

    return
